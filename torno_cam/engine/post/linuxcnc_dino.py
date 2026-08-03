# -*- coding: utf-8 -*-
"""Dialeto da maquina Dino (LinuxCNC 2.9.7) — corrige o que o pos fiel emite
de invalido. Usado pela UI (a UI NUNCA usa o LinuxCNCPost fiel).

Correcoes em relacao ao porte fiel:
- Rosca linha-a-linha: G33 X Z K<passo>  (o fiel emitia G32 F, inexistente)
- Comentarios: ASCII puro (sem Ø / acentos / travessao) — alguns setups do
  LinuxCNC engasgam com nao-ASCII entre parenteses
- Ciclo de FURACAO (G81/G82/G83): LIBERADO e corrigido — ver
  format_cycle_call. Validado no interpretador rs274 com o INI do torno.
- Demais ciclos fixos (desbaste G71 / canal G75 / rosca G76): bloqueados com
  mensagem PT-BR ate serem validados (Fase 3); a UI mantem esses toggles
  GERAR CICLO desabilitados

A furacao emite o RPM correto porque a UI passa RPM (nao Vc) no campo de
velocidade — ver defaults/DRILL e o painel de furacao."""

import unicodedata

from .linuxcnc import LinuxCNCPost
from .format_utils import word, gline
from ..jsutil import js_num


def _ascii(text):
    """Reduz o texto a ASCII: Ø -> '', travessoes -> '-', acentos removidos."""
    text = text.replace(u"Ø", "")          # Ø (diametro)
    text = text.replace(u"—", "-").replace(u"–", "-")  # — –
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    # colapsa espacos duplos que possam ter sobrado ao remover Ø
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()


class LinuxCNCDinoPost(LinuxCNCPost):
    name = "LinuxCNC Dino"
    dialect = "linuxcnc-dino"

    def format_comment(self, text):
        return "({})".format(_ascii(text))

    def format_tool_call(self, t):
        # A descricao do tool call tambem vai entre parenteses -> ASCII.
        from ..jsutil import js_num
        s = "T{} M6 G43 H{}".format(str(t.toolNumber).zfill(2), js_num(t.toolOffset))
        if t.description:
            s += " ({})".format(_ascii(t.description))
        return s

    def format_thread_feed(self, node):
        # G33 = movimento sincronizado com o fuso (K = passo por volta).
        return gline("G33", word("X", node.x), word("Z", node.z),
                     word("K", node.pitch))

    # ── Modo de trajetoria (precisao do movimento) ──────────────────────────
    # G64 P<tol>: mistura os movimentos mantendo o desvio da trajetoria dentro
    # da tolerancia. Sem isso o programa herda o modo que a maquina estiver —
    # se um programa anterior deixou G61 (parada exata, lento) ou um G64 sem P
    # (mistura livre, corta canto), o resultado muda sem aviso.
    # 0.01 mm: mais apertado que o RS274NGC_STARTUP_CODE do INI (G64 P0.025),
    # escolhido com o usuario para privilegiar precisao. Diminuir aperta mais
    # (mais desaceleracao nos cantos); 0 ou negativo emite G61 (trajetoria
    # exata, sem mistura nenhuma).
    TOLERANCIA_TRAJETORIA = 0.01

    def format_program_header(self, c):
        linhas = super(LinuxCNCDinoPost, self).format_program_header(c)
        tol = self.TOLERANCIA_TRAJETORIA
        if tol is None:
            return linhas
        if tol <= 0:
            linhas.append("G61  (TRAJETORIA EXATA)")
        else:
            linhas.append("G64 P{}  (TOLERANCIA DE TRAJETORIA)".format(js_num(tol)))
        return linhas

    # ── Troca de velocidade auto-suficiente (RUN FROM LINE) ─────────────────
    # O engine emite so "G96 S<acab>" ao passar do desbaste para o acabamento.
    # Isso conta com o estado modal deixado pelo bloco anterior — o que quebra
    # se o operador der RUN FROM LINE direto no acabamento: entra sem limite de
    # RPM (D), sem sentido do fuso (M3/M4) e sem refrigeracao.
    # Aqui a troca vira um bloco completo, entao qualquer secao pode ser o
    # ponto de partida do programa.
    def __init__(self):
        super(LinuxCNCDinoPost, self).__init__()
        self._sentido = "CW"
        self._rpm_max = None
        self._refrig = None

    def generate(self, config, operations):
        self._sentido, self._rpm_max, self._refrig = "CW", None, None
        return super(LinuxCNCDinoPost, self).generate(config, operations)

    def format_spindle_on(self, s):
        self._sentido = s.dir
        self._rpm_max = s.maxRPM
        return super(LinuxCNCDinoPost, self).format_spindle_on(s)

    def format_coolant_on(self, coolant_type):
        self._refrig = coolant_type
        return super(LinuxCNCDinoPost, self).format_coolant_on(coolant_type)

    def format_coolant_off(self):
        self._refrig = None
        return super(LinuxCNCDinoPost, self).format_coolant_off()

    def format_spindle_speed(self, s):
        m = "M3" if self._sentido == "CW" else "M4"
        if s.cssMode:
            val = s.sfm if s.sfm is not None else s.rpm
            rpm_max = self._rpm_max if self._rpm_max is not None else 5000
            linha = "G96 D{} S{} {}".format(js_num(rpm_max), js_num(val), m)
        else:
            linha = "G97 S{} {}".format(js_num(s.rpm), m)
        if self._refrig:
            linha += "\n" + super(LinuxCNCDinoPost, self).format_coolant_on(self._refrig)
        return linha

    # ── Ciclo de furacao (G81/G82/G83) ──────────────────────────────────────
    # Tres correcoes, todas verificadas no interpretador rs274 com o INI real:
    #
    # 1) PLANO: o ciclo fixo fura no eixo perpendicular ao plano ativo. Em G18
    #    (XZ) esse eixo e Y, que nao existe neste torno — o interpretador
    #    recusa com "Y value unspecified in xz plane canned cycle". Em G17 o
    #    eixo de furacao e Z, que e o certo aqui. Por isso G17 antes e G18 de
    #    volta depois do G80.
    # 2) PAUSA: o IR traz P em MILISSEGUNDOS (estilo Fanuc); no LinuxCNC o P do
    #    ciclo e em SEGUNDOS. Sem converter, "1 s" viraria 1000 s com a broca
    #    girando no fundo do furo.
    # 3) QUEM PAUSA: G81 e G83 aceitam P mas IGNORAM (nenhum DWELL na saida
    #    canonica). Quem pausa no fundo e o G82. Entao: com pausa e sem bicada
    #    -> G82; com bicada (G83) a pausa nao existe no LinuxCNC e o P e
    #    descartado em vez de ficar la enganando.
    def format_cycle_call(self, cycle):
        code = cycle.cycleCode
        pausa_s = (cycle.p / 1000.0) if cycle.p else None
        if code == "G81" and pausa_s:
            code = "G82"
        if code == "G83":
            pausa_s = None
        linha = gline(code, word("X", cycle.x), word("Z", cycle.z),
                      word("R", cycle.r), word("F", cycle.f),
                      word("Q", cycle.q), word("P", pausa_s))
        return "G17  (PLANO XY: EIXO DE FURACAO = Z)\n" + linha

    def format_cycle_cancel(self):
        return "G80\nG18  (VOLTA AO PLANO XZ DO TORNO)"

    def _canned_bloqueado(self):
        raise NotImplementedError(
            "Ciclo fixo ainda nao validado neste controlador (use modo manual)")

    def format_canned_rough_cycle(self, node):
        self._canned_bloqueado()

    def format_canned_groove_cycle(self, node):
        self._canned_bloqueado()

    # ── Ciclo de rosca G76 ──────────────────────────────────────────────────
    # Semantica verificada no interpretador rs274 com o INI do torno:
    #
    #   pico   = linha_de_referencia + I      (I<0 externa, I>0 interna; I=0
    #                                          nao gera passe NENHUM)
    #   1o passe = pico -/+ J
    #   final    = pico -/+ K
    #
    # E o mais importante: I/J/K seguem o MODO ATIVO — em G7 (diametro) sao
    # lidos como DIAMETRO, em G8 (raio) como raio. Medido no rs274, partindo
    # do mesmo ponto fisico (raio 11) com I-2.5 J0.2:
    #
    #   G8 -> 1o passe no raio 8.30   (11 - 2.5 - 0.2)
    #   G7 -> 1o passe no raio 9.65   (11 - 2.5/2 - 0.2/2)  = METADE
    #
    # O programa fica SEMPRE em G7 (nunca troca de modo no meio), entao os
    # valores saem em diametro: pico, primeiro passe e profundidade vao
    # dobrados. Conferido no interpretador: da exatamente os mesmos passes
    # que a versao antiga embrulhada em G8.
    #
    # Tres defeitos do pos original corrigidos aqui:
    #  1) I = -profundidade E K = profundidade -> o pico descia uma
    #     profundidade e ainda cortava outra = ROSCA COM O DOBRO DA
    #     PROFUNDIDADE. Agora I = deslocamento do pico (a folga de
    #     aproximacao), que e' o que poe o pico no diametro da rosca.
    #  2) Q vinha em decimos de grau (Fanuc). No LinuxCNC Q e' o angulo do
    #     carro em GRAUS — para fio de 60 graus usa-se 29.5.
    #  3) I tinha sinal fixo negativo, o que inverteria a rosca interna.
    def format_canned_thread_cycle(self, node):
        pico = getattr(node, "peakOffset", 0.0) or 0.0
        if pico == 0.0:
            # sem deslocamento o LinuxCNC nao gera passe; usa um minimo
            pico = -0.05
        interna = pico > 0
        prof = abs(node.threadDepth)
        primeiro = abs(node.firstCutDepth)
        angulo = node.threadAngle or 60.0
        carro = max(0.0, angulo / 2.0 - 0.5)     # 60 graus -> 29.5

        return gline(
            "G76",
            word("P", node.pitch),
            word("Z", node.finalZ),
            # x2: o engine calcula em raio e o programa esta em G7 (diametro)
            word("I", round(pico * 2.0, 4)),
            word("J", round(primeiro * 2.0, 4)),
            word("K", round(prof * 2.0, 4)),
            word("Q", round(carro, 4)),
            word("H", node.springPasses),
            "L0",
        )

    def _format_canned_thread_cycle_bloqueado(self, node):
        self._canned_bloqueado()
