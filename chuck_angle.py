#!/usr/bin/env python3
"""
chuck_angle.py - Angulo rotacional do spindle/placa (0-360 graus).

Le o sinal de revolucoes do encoder do spindle (spindle-revs) e calcula
o angulo relativo:  angle = (revs mod 1.0) * 360

Referencia 0 graus = posicao do spindle no startup do LinuxCNC (relativo).
O operador % do Python trata revs negativas (M4 reverso) corretamente:
  -0.25 % 1.0 = 0.75  ->  270.00 graus   (fmod do C daria -0.25, ERRADO)

Pinos HAL:
  chuckangle.revs    float IN   (revolucoes acumuladas, vem de spindle-revs)
  chuckangle.angle   float OUT  (angulo 0..360 graus)

Uso no HAL (postgui):
  loadusr -Wn chuckangle python3 chuck_angle.py
"""

import hal
import time

POLL_HZ = 20  # 20 Hz: suave para leitura visual do operador


def main():
    h = hal.component("chuckangle")
    h.newpin("revs",  hal.HAL_FLOAT, hal.HAL_IN)
    h.newpin("angle", hal.HAL_FLOAT, hal.HAL_OUT)
    h.ready()

    try:
        while True:
            revs = h["revs"]
            # Python % devolve sempre 0.0 <= frac < 1.0, mesmo para revs < 0
            h["angle"] = (revs % 1.0) * 360.0
            time.sleep(1.0 / POLL_HZ)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
