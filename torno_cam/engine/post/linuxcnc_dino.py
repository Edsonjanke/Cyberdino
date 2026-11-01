# -*- coding: utf-8 -*-
"""Dialeto da maquina Dino (LinuxCNC 2.9.7) — corrige o que o pos fiel emite
de invalido. Usado pela UI (a UI NUNCA usa o LinuxCNCPost fiel).

Correcoes em relacao ao porte fiel:
- Rosca linha-a-linha: G33 X Z K<passo>  (o fiel emitia G32 F, inexistente)
- Comentarios: ASCII puro (sem Ø / acentos / travessao) — alguns setups do
  LinuxCNC engasgam com nao-ASCII entre parenteses
- Comentarios sem parenteses por dentro: o LinuxCNC recusa o programa com
  "Nested comment found" (ex.: "(Passe 11 (mola) ...)", titulo "Eixo (A)")
- Ciclo de FURACAO (G81/G82/G83): LIBERADO e corrigido — ver
  format_cycle_call. Validado no interpretador rs274 com o INI do torno.
- Desbaste G71 / G72: LIBERADOS no formato do LinuxCNC 2.9 (perfil numa sub
  O-word), ver format_canned_rough_cycle. Validado no rs274 com o INI do torno.
- Canal G75: nao existe no LinuxCNC, continua bloqueado (a UI trava o toggle)

A furacao emite o RPM correto porque a UI passa RPM (nao Vc) no campo de
velocidade — ver defaults/DRILL e o painel de furacao."""

import re
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


# Comentarios que o engine escreve com parenteses por dentro (texto herdado
# do EvoCAM, mantido nas estrategias por causa da paridade com os goldens).
_COMENTARIOS_FIXOS = {
    u"--- Desbaste ID (passes longitudinais) ---":
        u"--- DESBASTE ID: PASSES LONGITUDINAIS ---",
}


def _sem_parenteses(text):
    """Tira '(' e ')' de dentro do comentario: 'Passe 11 (mola) prof=0.6'
    -> 'Passe 11: mola prof=0.6'. Vale para titulo e nome de ferramenta."""
    text = _COMENTARIOS_FIXOS.get(text, text)
    text = re.sub(r"\s*\(\s*", ": ", text)
    text = re.sub(r"\s*\)\s*", " ", text)
    return re.sub(r"^\s*:\s*", "", text)


class LinuxCNCDinoPost(LinuxCNCPost):
    name = "LinuxCNC Dino"
    dialect = "linuxcnc-dino"

    def format_comment(self, text):
        return "({})".format(_ascii(_sem_parenteses(text)))

    # ── G95 na primeira linha de avanco de cada operacao ────────────────────
    # O G95 do cabecalho e' modal: com RUN FROM LINE no meio do programa (ou
    # se um programa anterior deixou G94) a operacao herdaria o modo errado.
    # Cada operacao repete o modo e o F na primeira linha que avanca:
    # "G1 X22.533 Z-30 G95 F0.15". A troca de ferramenta abre a operacao.
    def modal_feed(self, feed):
        if feed is not None and self._avanco_pendente:
            self._last_feed = None          # forca o F nessa linha
        return self._com_modo(super(LinuxCNCDinoPost, self).modal_feed(feed))

    def _com_modo(self, palavra_f):
        if palavra_f and self._avanco_pendente:
            self._avanco_pendente = False
            return "{} {}".format(self._modo_avanco, palavra_f)
        return palavra_f

    def format_tool_call(self, t):
        self._avanco_pendente = True
        # A descricao do tool call tambem vai entre parenteses -> ASCII.
        from ..jsutil import js_num
        s = "T{} M6 G43 H{}".format(str(t.toolNumber).zfill(2), js_num(t.toolOffset))
        if t.description:
            s += " ({})".format(_ascii(_sem_parenteses(t.description)))
        return s

    # Passo com 5 casas: em polegada 25.4/fios nao fecha (14 fios = 1.814286)
    # e 3 casas acumulam erro ao longo da rosca (GCODE-ROSCAS.md, 9.1).
    CASAS_PASSO = 5

    def format_thread_feed(self, node):
        # G33 = movimento sincronizado com o fuso (K = passo por volta).
        return gline("G33", word("X", node.x), word("Z", node.z),
                     word("K", node.pitch, self.CASAS_PASSO))

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
        # 1a linha = titulo digitado pelo operador: passa pelo mesmo filtro
        linhas[0] = self.format_comment(c.title)
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
        self._sub = 0
        self._modo_avanco = "G95"
        self._avanco_pendente = False

    def generate(self, config, operations):
        self._sentido, self._rpm_max, self._refrig = "CW", None, None
        self._sub = 0
        self._modo_avanco = "G94" if config.feedMode == "MIN" else "G95"
        self._avanco_pendente = False
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
                      word("R", cycle.r), self._com_modo(word("F", cycle.f)),
                      word("Q", cycle.q), word("P", pausa_s))
        return "G17  (PLANO XY: EIXO DE FURACAO = Z)\n" + linha

    def format_cycle_cancel(self):
        return "G80\nG18  (VOLTA AO PLANO XZ DO TORNO)"

    def _canned_bloqueado(self):
        raise NotImplementedError(
            "Ciclo fixo ainda nao validado neste controlador (use modo manual)")

    # ── Desbaste G71 (eixo Z) / G72 (faceamento) do LinuxCNC 2.9 ────────────
    # Formato: G71 Q<sub> D<sobremetal> I<passo> R<recuo> F<avanco>, com o
    # perfil acabado numa sub O<sub>. O ciclo parte do ponto em que a
    # ferramenta esta (a estrategia posiciona antes). Medido no rs274 com o
    # INI do torno, em G7:
    #   - I, D e R sao em RAIO (I2.5 -> passes de 5 em 5 no diametro);
    #   - D vale em X e em Z (o ultimo passe para D antes da parede e do fundo);
    #   - o 1o passe corre no proprio ponto inicial; no fim o ciclo percorre o
    #     perfil e volta ao X inicial no Z do fim do perfil;
    #   - interno funciona (X crescendo; o recuo vai para o centro).
    # A sub vem antes da chamada, no meio do programa: o interpretador pula a
    # definicao quando passa por ela. Um numero de sub por ciclo no programa.
    def format_canned_rough_cycle(self, node):
        self._sub += 1
        n = 100 + self._sub
        codigo = node.cycleCode or "G71"
        if node.finishStockZ:
            sobra = abs(node.finishStockZ)
        else:
            sobra = abs(node.finishStockX or 0) / 2.0
        linhas = ["O{} sub".format(n)]
        for m in node.profile:
            if m.type == "LINEAR":
                linhas.append(gline("G1", word("X", m.x), word("Z", m.z)))
            else:
                linhas.append(gline("G2" if m.dir == "CW" else "G3",
                                    word("X", m.x), word("Z", m.z),
                                    word("I", m.i), word("K", m.k)))
        linhas.append("O{} endsub".format(n))
        linhas.append(gline(codigo, "Q{}".format(n), word("D", round(sobra, 4)),
                            word("I", node.depthOfCut), word("R", node.retract),
                            self._com_modo(word("F", node.roughFeed))))
        if node.generateFinish:
            linhas.append(gline("G70", "Q{}".format(n), word("F", node.finishFeed)))
        return "\n".join(linhas)

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
    #
    # R2 (2026-11-01, pedido do Edson): sem R o LinuxCNC usa R1, profundidade
    # CONSTANTE em todo passe (J, 2J, 3J...), e os passes do fundo ficam os
    # mais pesados. R2 = reducao de AREA constante, como diz a tela da rosca e
    # como o modo linha a linha ja faz. Medido no rs274 (M10x1,5, J0.6): sem R
    # 6 passes (9.4, 8.8, 8.2, fundo); com R2 12 passes cada vez mais finos.
    #
    # L2 (2026-11-01): rampa de saida com E = passo. Medido no rs274 (M10x1,5,
    # Z-20, E1.5): o fundo vai ate Z-18.5 e a rampa sincronizada sobe ate a
    # crista em Z-20. Nao passa do FIM Z e dispensa o canal de saida.
    DEGRESSAO_G76 = 2.0

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
        # L2: rampa so na saida, ao longo de E (2026-11-01, pedido do Edson)
        rampa = getattr(node, "exitTaper", 0.0) or 0.0

        return gline(
            "G76",
            word("P", node.pitch, self.CASAS_PASSO),
            word("Z", node.finalZ),
            # x2: o engine calcula em raio e o programa esta em G7 (diametro)
            word("I", round(pico * 2.0, 4)),
            word("J", round(primeiro * 2.0, 4)),
            word("R", self.DEGRESSAO_G76),
            word("K", round(prof * 2.0, 4)),
            word("Q", round(carro, 4)),
            word("H", node.springPasses),
            word("E", rampa, 4) if rampa > 0 else "",
            "L2" if rampa > 0 else "L0",
        )

    def _format_canned_thread_cycle_bloqueado(self, node):
        self._canned_bloqueado()
