#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Descobre em QUAL GPIO esta ligado um botao ou volante do painel.

Existe porque ja' custou uma viagem a' maquina: o volante do Z foi parar
num par de pinos onde nao havia nada e simplesmente ficou mudo, sem erro
nenhum. Em vez de deduzir a fiacao, aperta e olha.

Uso (com o LinuxCNC JA' RODANDO, maquina ligada ou nao):

    python3 tools/acha_gpio.py            # 15 s olhando tudo
    python3 tools/acha_gpio.py 30         # 30 s

Durante a contagem: aperte o botao, ou gire o volante, que voce quer
achar. No fim ele lista so' os pinos que mudaram, do que mais mudou pro
que menos mudou — um volante da' dezenas de trocas, um botao da' duas
(aperta e solta).

Nao escreve nada em lugar nenhum: so' le pinos.
"""

import sys
import time

import hal

INTERVALO = 0.005          # 200 Hz: pega detente de volante sem perder borda


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


def main():
    segundos = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0

    nomes = pinos_gpio()
    if not nomes:
        print("Nao achei pinos de GPIO. O LinuxCNC esta rodando?")
        print("(este script le a HAL da sessao em andamento)")
        return 1

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
