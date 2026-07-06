#!/usr/bin/env python3
"""
CyberDino - Contador de pecas
Incrementa apenas via M101 (rising edge no pin trigger).
Persiste em arquivo entre sessoes.

Pinos HAL:
  partcounter.trigger  bit IN   (rising edge incrementa - usado por M101)
  partcounter.reset    bit IN   (rising edge zera contador)
  partcounter.preset   u32 IN   (valor a carregar quando load pulsar)
  partcounter.load     bit IN   (rising edge: count = preset)
  partcounter.count    s32 OUT  (numero atual de pecas)

Uso no HAL:
  loadusr -Wn partcounter python3 partcounter.py
"""

import hal
import time
import os

COUNT_FILE = "/home/evo/linuxcnc/configs/Dino_Evo/parts_count.txt"
POLL_HZ = 10  # 10 Hz e suficiente; M30 dura segundos

# Carregar contagem persistida
def load_count():
    try:
        with open(COUNT_FILE) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0

def save_count(n):
    try:
        with open(COUNT_FILE, "w") as f:
            f.write(str(n))
    except Exception as e:
        print(f"partcounter: erro salvando: {e}")

def main():
    h = hal.component("partcounter")
    h.newpin("trigger", hal.HAL_BIT, hal.HAL_IN)
    h.newpin("reset",   hal.HAL_BIT, hal.HAL_IN)
    h.newpin("preset",  hal.HAL_U32, hal.HAL_IN)
    h.newpin("load",    hal.HAL_BIT, hal.HAL_IN)
    h.newpin("count",   hal.HAL_S32, hal.HAL_OUT)
    h.ready()

    count = load_count()
    h["count"] = count
    print(f"partcounter: iniciado com count={count}")

    prev_trigger = False
    prev_reset = False
    prev_load = False

    try:
        while True:
            trigger = h["trigger"]
            reset = h["reset"]
            load = h["load"]

            # Borda de subida do trigger: M101 pulsou
            if trigger and not prev_trigger:
                count += 1
                h["count"] = count
                save_count(count)
                print(f"partcounter: peca completada (M101), count={count}")

            # Borda de subida do load: aplica preset digitado
            if load and not prev_load:
                count = int(h["preset"])
                h["count"] = count
                save_count(count)
                print(f"partcounter: count carregado com preset={count}")

            # Borda de subida do reset: zera
            if reset and not prev_reset:
                count = 0
                h["count"] = count
                save_count(count)
                print("partcounter: contador resetado")

            prev_trigger = trigger
            prev_reset = reset
            prev_load = load

            time.sleep(1.0 / POLL_HZ)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
