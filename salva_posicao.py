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
import signal
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))

# Prefixo opcional (1o argumento): o sim roda com "sim_" pra NAO sobrescrever
# a posicao da maquina de verdade. Jogar no sim nao pode mexer no ponto de
# partida do torno.
PREFIXO = sys.argv[1] if len(sys.argv) > 1 else ""

ARQ_JSON = os.path.join(AQUI, PREFIXO + "posicao_salva.json")

# Bandeira criada pelo botao REFERENCIAR NA CHAVE (aba CUSTOMS) ou pelo
# referenciar_na_chave.sh. Quem escreve nos .inc e' SO este componente —
# senao o botao armava a chave e o encerramento regravava a posicao por
# cima, desarmando sozinho.
ARQ_BANDEIRA = os.path.join(AQUI, PREFIXO + "armar_chave.flag")

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


def grava(posicoes, motivo):
    """Grava os .inc de cada joint e o json de acompanhamento."""
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

    # Bandeira que sobrou da sessao passada nao vale: o INI ja foi lido.
    if os.path.exists(ARQ_BANDEIRA):
        try:
            os.remove(ARQ_BANDEIRA)
        except OSError:
            pass

    def ao_encerrar(_sig=None, _frame=None):
        """SIGTERM: o LinuxCNC esta fechando. Ultima gravada antes de sair."""
        if estado["ultima"] is not None and not estado["modo_chave"]:
            grava(estado["ultima"], "encerramento")
        comp.exit()
        sys.exit(0)

    signal.signal(signal.SIGTERM, ao_encerrar)
    signal.signal(signal.SIGINT, ao_encerrar)

    periodo = 1.0 / POLL_HZ
    while True:
        time.sleep(periodo)

        # Pediram referenciamento na chave: escreve os moldes e para de
        # salvar ate o proximo boot (inclusive no encerramento).
        if not estado["modo_chave"] and os.path.exists(ARQ_BANDEIRA):
            try:
                arma_chave()
                os.remove(ARQ_BANDEIRA)
                estado["modo_chave"] = True
                print("salva_posicao: referenciamento na chave armado "
                      "para o proximo boot")
            except Exception as e:
                print("salva_posicao: erro armando a chave: %s" % e,
                      file=sys.stderr)
        if estado["modo_chave"]:
            continue

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
