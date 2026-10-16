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

Durante a contagem: aperte o botao, ou gire o volante, que voce quer
achar. No fim ele lista so' os pinos que mudaram, do que mais mudou pro
que menos mudou — um volante da' dezenas de trocas, um botao da' duas
(aperta e solta).

Nao escreve nada em lugar nenhum: so' le pinos.
"""

import os
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


def main():
    guiado = "--painel" in sys.argv
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    segundos = float(argumentos[0]) if argumentos else 15.0

    try:
        comp = liga_na_hal()
    except Exception as e:
        print("Nao consegui entrar na HAL: %s" % e)
        print("O LinuxCNC esta rodando? (este script le a sessao em andamento)")
        return 1
    try:
        return _rodar(guiado, segundos)
    finally:
        try:
            comp.exit()
        except Exception:
            pass


def _rodar(guiado, segundos):
    nomes = pinos_gpio()
    if not nomes:
        print("Nao achei pinos de GPIO. O firmware desta placa expoe GPIO?")
        return 1

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
