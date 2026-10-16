#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Descobre em QUAL GPIO esta ligado um botao ou volante do painel.

Existe porque ja' custou uma viagem a' maquina: o volante do Z foi parar
num par de pinos onde nao havia nada e simplesmente ficou mudo, sem erro
nenhum. Em vez de deduzir a fiacao, aperta e olha.

Uso (com o LinuxCNC JA' RODANDO, maquina ligada ou nao):

    python3 tools/acha_gpio.py            # 15 s olhando tudo
    python3 tools/acha_gpio.py 30         # 30 s
    python3 tools/acha_gpio.py --painel   # guiado: pede um controle por vez
                                          # e monta o mapa inteiro
    python3 tools/acha_gpio.py --livres   # so' as entradas que a config nao
                                          # usa: diz se sao entrada ou saida
                                          # e vigia pra ver se dao sinal

Durante a contagem: aperte o botao, ou gire o volante, que voce quer
achar. No fim ele lista so' os pinos que mudaram, do que mais mudou pro
que menos mudou — um volante da' dezenas de trocas, um botao da' duas
(aperta e solta).

Nao escreve nada em lugar nenhum: so' le pinos.
"""

import os
import re
import subprocess
import sys
import time

import hal

INTERVALO = 0.005          # 200 Hz: pega detente de volante sem perder borda


def liga_na_hal():
    """Cria um componente proprio — sem isso o hal.get_value NAO funciona.

    O modulo hal do LinuxCNC responde "Cannot call before creating
    component" a qualquer leitura feita por um processo que nao se
    registrou na HAL. O erro e' silencioso pra quem so' tenta ler pinos
    num try/except: parece que nenhum pino existe. Foi o que aconteceu na
    primeira versao deste script."""
    nome = "achagpio%d" % os.getpid()
    comp = hal.component(nome)
    comp.ready()
    return comp


def pinos_gpio():
    """Todos os hm2_*.gpio.NNN.in que existem nesta sessao."""
    achados = []
    for placa in ("hm2_7i92.0", "hm2_5i25.0", "hm2_7i76e.0"):
        for n in range(64):
            nome = "%s.gpio.%03d.in" % (placa, n)
            try:
                hal.get_value(nome)
            except Exception:
                continue
            achados.append(nome)
        if achados:
            break
    return achados


# Os controles do painel, na ordem em que o modo guiado pergunta.
# (nome que aparece na tela, quantos pinos esperar)
PAINEL = (
    ("CYCLE START", 1),
    ("PAUSE", 1),
    ("RESET", 1),
    ("AUTO", 1),
    ("MANUAL", 1),
    ("MPG (liga/desliga)", 1),
    ("RODAR DA LINHA", 1),
    ("REFRIGERANTE", 1),
    ("VOLANTE DO X (gire)", 2),
    ("VOLANTE DO Z (gire)", 2),
)


def espera_mexer(nomes, anterior, limite=20.0, quietos=1.0):
    """Espera alguem mexer e devolve {pino: trocas}.

    Para de contar depois de `quietos` segundos sem nenhuma troca — assim
    o operador aperta, solta, e o programa segue sozinho."""
    trocas = {}
    inicio = time.time()
    ultima = None
    while True:
        agora = time.time()
        if ultima is None and agora - inicio > limite:
            return {}
        if ultima is not None and agora - ultima > quietos:
            return trocas
        for n in nomes:
            try:
                v = hal.get_value(n)
            except Exception:
                continue
            if v != anterior[n]:
                anterior[n] = v
                trocas[n] = trocas.get(n, 0) + 1
                ultima = agora
        time.sleep(INTERVALO)


def modo_guiado(nomes):
    """Pergunta um controle por vez e monta o mapa do painel."""
    anterior = {n: hal.get_value(n) for n in nomes}
    mapa = []
    print("Modo guiado: aperte (ou gire) o que for pedido e espere a")
    print("proxima pergunta. ENTER sem mexer em nada pula o item.\n")
    for rotulo, quantos in PAINEL:
        input("  >>> %s  — aperte agora, depois espere... " % rotulo)
        achou = espera_mexer(nomes, anterior)
        if not achou:
            print("      (nada mudou — pulado)\n")
            mapa.append((rotulo, []))
            continue
        ordenado = sorted(achou.items(), key=lambda kv: -kv[1])[:quantos]
        pinos = [(n.split(".gpio.")[1].split(".")[0], c) for n, c in ordenado]
        print("      %s\n" % "  ".join("GPIO.%s (%d trocas)" % (g, c)
                                        for g, c in pinos))
        mapa.append((rotulo, [g for g, _c in pinos]))

    print("\n=== MAPA DO PAINEL ===")
    for rotulo, pinos in mapa:
        print("  %-22s %s" % (rotulo, ", ".join("GPIO.%s" % g for g in pinos)
                              or "(nao achado)"))
    usados = {g for _r, ps in mapa for g in ps}
    livres = sorted(n.split(".gpio.")[1].split(".")[0] for n in nomes)
    print("\nEntradas que ninguem usou nesta rodada:")
    print("  " + ", ".join("GPIO.%s" % g for g in livres if g not in usados))
    return 0


def pinos_ligados():
    """GPIOs que a configuracao em uso ja' pegou (tem sinal no .in ou .in_not).

    Sai do proprio halcmd: a seta '==>' aparece quando o pino esta ligado a
    um sinal. Assim a lista de livres acompanha o custom.hal sozinha."""
    try:
        texto = subprocess.check_output(["halcmd", "show", "pin",
                                         "hm2_7i92.0.gpio"],
                                        stderr=subprocess.DEVNULL)
    except Exception:
        return set()
    usados = set()
    for linha in texto.decode("utf-8", "replace").split("\n"):
        if "==>" not in linha and "<==" not in linha:
            continue
        m = re.search(r"\.gpio\.(\d+)\.", linha)
        if m:
            usados.add(m.group(1))
    return usados


# Pinos que NAO estao reservados a stepgen / PWM / encoder neste firmware.
#
# O hostmot2 exporta `gpio.NNN` para TODOS os 34 I/O, inclusive os que ele
# usa como passo/direcao e como encoder — se a gente listasse tudo, a
# ferramenta mandaria o operador encostar +5V num pino de stepgen, que e'
# saida. Esta lista sai do mapa do firmware:
#
#   mesaflash --device 7i92 --addr 10.10.10.10 --readhmid
#
# com a config em uso (num_encoders=2 num_pwmgens=1 num_stepgens=4):
#   em uso por modulo: 0 (PWM0), 2,4,5,6,7,8,9,10 (StepGen 0..3),
#                      14,15,16 (QCount0 = spindle), 17,18,19 (QCount1)
#   sobra como GPIO  : 1, 3, 11, 12, 13, 20..33
#
# Dos que sobram, 20..27 e 30,31 ja' tem botao/volante; 16 e 26 sao o
# volante do Z. Entao os candidatos de verdade sao poucos — mas a lista
# abaixo e' a dos que o firmware NAO reserva, e o resto do filtro
# (ja' ligado a um sinal / marcado como saida) tira o que falta.
CANDIDATOS = ("001", "003", "011", "012", "013",
              "020", "021", "022", "023", "024", "025", "026", "027",
              "028", "029", "030", "031", "032", "033")


def modo_livres(nomes, segundos):
    """Mostra as entradas que ninguem usa e vigia se alguma da' sinal."""
    usados = pinos_ligados()
    livres = [n for n in nomes
              if n.split(".gpio.")[1].split(".")[0] in CANDIDATOS
              and n.split(".gpio.")[1].split(".")[0] not in usados]
    if not livres:
        print("Nenhuma entrada livre: a configuracao usa todas as que o")
        print("firmware deixa como GPIO.")
        return 0

    print("Entradas que a configuracao NAO usa:\n")
    print("  %-10s %-9s %-8s %s" % ("pino", "direcao", "repouso", "serve pra botao?"))
    for n in livres:
        g = n.split(".gpio.")[1].split(".")[0]
        try:
            saida = hal.get_value("hm2_7i92.0.gpio.%s.is_output" % g)
        except Exception:
            saida = None
        valor = hal.get_value(n)
        if saida:
            serve = "NAO - esta como SAIDA, nao encoste nada"
        elif valor:
            serve = "sim - tem pull-up: botao pro GND funciona"
        else:
            serve = "so' ligando no +5V (nao tem pull-up)"
        print("  GPIO.%-5s %-9s %-8s %s"
              % (g, "saida" if saida else "entrada",
                 "1" if valor else "0", serve))

    print("\nAgora encoste um fio em cada um desses pontos por ~2 s, um de")
    print("cada vez. Use +5V (DB15 pino 15) nos que leem 0, e GND (pino 14)")
    print("nos que leem 1. NAO encoste nada em pino marcado como SAIDA.")
    print("\nVigiando por %.0f s...\n" % segundos)

    ant = {n: hal.get_value(n) for n in livres}
    t0 = time.time()
    mexeram = {}
    while time.time() - t0 < segundos:
        for n in livres:
            try:
                v = hal.get_value(n)
            except Exception:
                continue
            if v != ant[n]:
                ant[n] = v
                g = n.split(".gpio.")[1].split(".")[0]
                mexeram[g] = mexeram.get(g, 0) + 1
                print("  %6.1fs  GPIO.%s -> %s" % (time.time()-t0, g,
                                                   "1" if v else "0"))
        time.sleep(INTERVALO)

    print("\n=== RESULTADO ===")
    if not mexeram:
        print("Nenhuma das entradas livres reagiu.")
        print("Ou o fio nao chegou nelas, ou o ponto na placa nao esta")
        print("ligado ao FPGA (acontece nesta BOB chinesa).")
    else:
        for g, c in sorted(mexeram.items(), key=lambda kv: -kv[1]):
            print("  GPIO.%s respondeu (%d trocas) — SERVE" % (g, c))
    return 0


def main():
    guiado = "--painel" in sys.argv
    livres = "--livres" in sys.argv
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    segundos = float(argumentos[0]) if argumentos else 15.0

    try:
        comp = liga_na_hal()
    except Exception as e:
        print("Nao consegui entrar na HAL: %s" % e)
        print("O LinuxCNC esta rodando? (este script le a sessao em andamento)")
        return 1
    try:
        return _rodar(guiado, livres, segundos)
    finally:
        try:
            comp.exit()
        except Exception:
            pass


def _rodar(guiado, livres, segundos):
    nomes = pinos_gpio()
    if not nomes:
        print("Nao achei pinos de GPIO. O firmware desta placa expoe GPIO?")
        return 1

    if livres:
        return modo_livres(nomes, segundos if segundos != 15.0 else 60.0)
    if guiado:
        return modo_guiado(nomes)

    print("Olhando %d entradas por %.0f s." % (len(nomes), segundos))
    print(">>> APERTE O BOTAO ou GIRE O VOLANTE agora <<<\n")

    anterior = {n: hal.get_value(n) for n in nomes}
    trocas = {n: 0 for n in nomes}

    fim = time.time() + segundos
    while time.time() < fim:
        for n in nomes:
            try:
                v = hal.get_value(n)
            except Exception:
                continue
            if v != anterior[n]:
                trocas[n] += 1
                anterior[n] = v
        time.sleep(INTERVALO)

    mexeram = sorted(((c, n) for n, c in trocas.items() if c), reverse=True)
    if not mexeram:
        print("Nenhuma entrada mudou.")
        print("Se voce mexeu mesmo, o fio nao esta chegando na placa —")
        print("ou esta num pino que o firmware nao expoe como GPIO.")
        return 0

    print("Mudaram:")
    for c, n in mexeram:
        numero = n.split(".gpio.")[1].split(".")[0]
        print("  GPIO.%s  %4d trocas   %s" % (numero, c, n))
    print("\nVolante: espere DOIS pinos com contagem parecida (fases A e B).")
    print("Botao:   espere UM pino com 2 trocas por aperto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
