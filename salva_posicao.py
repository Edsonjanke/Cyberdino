#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CyberDino - Salva a posicao de maquina para ligar sem referenciar.

Grava a posicao dos joints enquanto a maquina trabalha. No boot seguinte o
INI le esses valores por #INCLUDE e o REFERENCIAR adota a posicao salva sem
mover nada ("Immediate Homing", manual do LinuxCNC 2.9 secao 4.5.6.14):

    HOME_SEARCH_VEL = 0   -> "assume that the current location is the home
    HOME_LATCH_VEL  = 0      position for the machine"

Pinos HAL:
  salvaposicao.x-pos     float IN   joint.0.pos-fb (posicao de MAQUINA)
  salvaposicao.z-pos     float IN   joint.1.pos-fb
  salvaposicao.x-homed   bit   IN   halui.joint.0.is-homed
  salvaposicao.z-homed   bit   IN   halui.joint.1.is-homed

Uso no HAL (postgui):
  loadusr -Wn salvaposicao python3 salva_posicao.py

Quando grava:
  - a cada 500 ms ENQUANTO o eixo se move (limita o erro se o LinuxCNC
    morrer no meio de um movimento);
  - uma vez a mais quando o movimento PARA (ai o valor fica exato);
  - no SIGTERM, que e' como o LinuxCNC encerra ao fechar.
  Parado e sem mudanca nao grava nada.

So grava com os DOIS eixos referenciados: posicao de maquina sem referencia
nao significa nada.

Escrita atomica (arquivo temporario + rename): se faltar energia no meio da
gravacao, o .inc que o INI vai ler no boot seguinte continua inteiro — um
.inc truncado impediria o LinuxCNC de subir.
"""

import hal
import io
import json
import os
import re
import signal
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))

# Prefixo opcional (1o argumento): o sim roda com "sim_" pra NAO sobrescrever
# a posicao da maquina de verdade. Jogar no sim nao pode mexer no ponto de
# partida do torno.
PREFIXO = sys.argv[1] if len(sys.argv) > 1 else ""

ARQ_JSON = os.path.join(AQUI, PREFIXO + "posicao_salva.json")

# ESTADO do referenciamento: "chave" ou "posicao". Quem muda e' o botao da
# aba CUSTOMS ou o referenciar_na_chave.sh; este componente OBEDECE.
#
# Era uma bandeira de uma vez so, atendida pelo componente — e dependia de
# tempo: o botao reiniciava antes do atendimento e o encerramento gravava a
# posicao por cima. Quebrou duas vezes na maquina (04/10). Agora o estado
# fica no disco e e' relido ANTES DE CADA GRAVACAO, inclusive na saida.
ARQ_MODO = os.path.join(AQUI, PREFIXO + "modo_referenciamento.txt")

# Marca deixada ao armar a chave: a interface le no boot seguinte pra avisar
# o operador que agora o referenciamento e' o fisico, e apaga.
ARQ_MARCA = os.path.join(AQUI, PREFIXO + "chave_armada.marca")


ARQ_LOG = os.path.join(AQUI, PREFIXO + "log_referenciamento.txt")


def registra(texto):
    """Diario do referenciamento: sem ele, uma falha so' aparece como 'nao
    funcionou' e a investigacao vira adivinhacao (ja custou duas rodadas)."""
    try:
        with open(ARQ_LOG, "a") as fh:
            fh.write("%s  componente  %s\n"
                     % (time.strftime("%Y-%m-%d %H:%M:%S"), texto))
    except Exception:
        pass


INI_EM_USO = os.environ.get("INI_FILE_NAME") or ""


def homing_do_ini_em_uso():
    """Como o JOINT_0 esta configurado no INI QUE VALE nesta sessao.

    Devolve "chave", "posicao" ou None. Serve de conferencia: o LinuxCNC roda
    a partir de um .ini.expanded gerado no boot, e ja aconteceu de uma sessao
    subir com um expandido VELHO (reinicio feito com o proprio .expanded).
    Nesse caso o estado dizia "chave" e a maquina referenciava parado."""
    try:
        texto = io.open(INI_EM_USO, encoding="utf-8", errors="replace").read()
    except (IOError, OSError):
        return None
    bloco = re.search(r"\[JOINT_0\](.*?)(?=\n\[|\Z)", texto, re.S)
    if not bloco:
        return None
    vel = re.search(r"^HOME_SEARCH_VEL\s*=\s*([-\d.]+)", bloco.group(1), re.M)
    if vel is None:
        return "posicao"            # ausente = zero = referenciar parado
    return "posicao" if float(vel.group(1)) == 0 else "chave"


def modo_ref():
    """"chave" (busca fisica no proximo boot) ou "posicao" (padrao)."""
    try:
        return io.open(ARQ_MODO, encoding="utf-8").read().strip().lower()
    except (IOError, OSError):
        return "posicao"


def define_modo(valor):
    escreve_atomico(ARQ_MODO, valor + "\n")

# (nome do pino, arquivo .inc, numero da sequencia de referenciamento)
JOINTS = (
    ("x", os.path.join(AQUI, PREFIXO + "home_joint0.inc"), 1),
    ("z", os.path.join(AQUI, PREFIXO + "home_joint1.inc"), 2),
)

POLL_HZ = 10            # 10 Hz de leitura
INTERVALO_MOVENDO = 0.5  # grava no maximo a cada 500 ms enquanto anda
PARADO_MM = 0.0005       # abaixo disso o eixo e' considerado parado


def escreve_atomico(caminho, texto):
    """tmp + rename: o leitor nunca ve arquivo pela metade."""
    tmp = caminho + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(texto)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, caminho)


def bloco_inc(eixo, posicao, sequencia, quando):
    """Bloco de homing do INI, no formato Immediate Homing."""
    return (
        "# GERADO POR salva_posicao.py — NAO EDITAR A MAO\n"
        "# Posicao de maquina do eixo %s salva em %s\n"
        "# Referenciar com estes valores NAO move o eixo: so' assume que\n"
        "# ele esta onde foi deixado (manual 2.9, 4.5.6.14).\n"
        "# Para referenciar na chave de verdade: ./referenciar_na_chave.sh\n"
        "HOME = %.6f\n"
        "HOME_OFFSET = %.6f\n"
        "HOME_SEARCH_VEL = 0\n"
        "HOME_LATCH_VEL = 0\n"
        "HOME_USE_INDEX = NO\n"
        "HOME_SEQUENCE = %d\n"
        % (eixo.upper(), quando, posicao, posicao, sequencia)
    )


def arma_chave():
    """Copia os blocos de busca na chave para os .inc ativos."""
    for n, (_eixo, destino, _seq) in enumerate(JOINTS):
        molde = os.path.join(AQUI, "home_chave_joint%d.inc" % n)
        escreve_atomico(destino, io.open(molde, encoding="utf-8").read())
    escreve_atomico(ARQ_MARCA, time.strftime("%Y-%m-%d %H:%M:%S") + "\n")


def grava(posicoes, motivo):
    """Grava os .inc de cada joint e o json de acompanhamento.

    Rele o estado antes de escrever: se alguem pediu a chave entre a decisao
    e a escrita, nao sobrescreve."""
    if modo_ref() == "chave":
        return
    agora = time.time()
    quando = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(agora))
    try:
        for (eixo, arquivo, sequencia), pos in zip(JOINTS, posicoes):
            escreve_atomico(arquivo, bloco_inc(eixo, pos, sequencia, quando))
        escreve_atomico(ARQ_JSON, json.dumps({
            "posicao": {eixo: round(pos, 6)
                        for (eixo, _a, _s), pos in zip(JOINTS, posicoes)},
            "salvo_em": quando,
            "epoch": round(agora, 1),
            "motivo": motivo,
        }, indent=2) + "\n")
    except Exception as e:
        print("salva_posicao: erro gravando: %s" % e, file=sys.stderr)


def main():
    comp = hal.component("salvaposicao")
    for eixo, _arq, _seq in JOINTS:
        comp.newpin("%s-pos" % eixo, hal.HAL_FLOAT, hal.HAL_IN)
        comp.newpin("%s-homed" % eixo, hal.HAL_BIT, hal.HAL_IN)
    comp.ready()

    estado = {"ultima": None, "ultimo_write": 0.0, "movia": False,
              "modo_chave": False}

    # Este boot subiu em modo chave? Entao a maquina ainda vai referenciar
    # fisicamente: nao se escreve nada ate isso acontecer.
    pedido = modo_ref()
    vigente = homing_do_ini_em_uso()
    registra("boot: estado=%s | INI em uso=%s | %s"
             % (pedido, vigente, os.path.basename(INI_EM_USO)))
    esperando_chave = pedido == "chave"
    if esperando_chave and vigente == "posicao":
        # a chave esta armada mas ESTA sessao subiu em modo posicao: o
        # referenciamento daqui nao e' o fisico. Nao salva e nao desarma —
        # o pedido continua de pe pro proximo boot, feito do jeito certo.
        esperando_chave = False
        registra("ATENCAO: chave armada mas o INI desta sessao referencia "
                 "parado (expandido velho?). Pedido mantido para o proximo boot.")

    def ao_encerrar(_sig=None, _frame=None):
        registra("encerrando (modo=%s)" % modo_ref())
        """SIGTERM: o LinuxCNC esta fechando. Ultima gravada antes de sair.

        grava() rele o estado, entao um pedido de chave feito segundos antes
        de fechar NAO e' desfeito aqui."""
        if estado["ultima"] is not None:
            grava(estado["ultima"], "encerramento")
        comp.exit()
        sys.exit(0)

    signal.signal(signal.SIGTERM, ao_encerrar)
    signal.signal(signal.SIGINT, ao_encerrar)

    periodo = 1.0 / POLL_HZ
    while True:
        time.sleep(periodo)

        try:
            referenciados = all(comp["%s-homed" % eixo]
                                for eixo, _a, _s in JOINTS)
            posicoes = [comp["%s-pos" % eixo] for eixo, _a, _s in JOINTS]
        except Exception:
            continue
        if not referenciados:
            # sem referencia a posicao de maquina nao vale nada: nao grava e
            # nao perde o que ja estava salvo
            estado["ultima"] = None
            continue

        if esperando_chave:
            # o operador acabou de referenciar NA CHAVE: o pedido foi
            # cumprido, volta a salvar a posicao a partir daqui
            esperando_chave = False
            define_modo("posicao")
            registra("referenciamento fisico concluido em X=%.3f Z=%.3f; "
                     "voltando a salvar" % (posicoes[0], posicoes[1]))

        if modo_ref() == "chave":
            # pediram a chave nesta sessao (botao): nao escreve mais nada
            continue

        anterior = estado["ultima"]
        estado["ultima"] = posicoes
        if anterior is None:
            grava(posicoes, "referenciado")
            estado["ultimo_write"] = time.time()
            continue

        andou = any(abs(a - b) > PARADO_MM for a, b in zip(posicoes, anterior))
        agora = time.time()
        if andou:
            estado["movia"] = True
            if agora - estado["ultimo_write"] >= INTERVALO_MOVENDO:
                grava(posicoes, "em movimento")
                estado["ultimo_write"] = agora
        elif estado["movia"]:
            # acabou de parar: grava o valor exato e para de gravar
            grava(posicoes, "parado")
            estado["ultimo_write"] = agora
            estado["movia"] = False


if __name__ == "__main__":
    main()
