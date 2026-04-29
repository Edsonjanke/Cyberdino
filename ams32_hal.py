#!/usr/bin/env python3
"""
ams32_hal.py - Componente HAL para AMS32 (Delta DVP clone) via Modbus ASCII
Substitui mb2hal para comunicacao ASCII que o mb2hal nao suporta.

Pins HAL criados:
  ams32.cmd.00-07       (bit IN)  - Comandos LinuxCNC -> PLC (M100-M107)
  ams32.status.00-15    (bit OUT) - Status PLC -> LinuxCNC (M200-M215)
  ams32.spindle-rpm     (float IN)- RPM para o PLC (D100)
  ams32.pos-cmd-x       (float IN)- Posicao X atual (para salvar no PLC)
  ams32.pos-cmd-z       (float IN)- Posicao Z atual (para salvar no PLC)
  ams32.pos-saved-x     (float OUT)- Posicao X salva no PLC (lida no startup)
  ams32.pos-saved-z     (float OUT)- Posicao Z salva no PLC (lida no startup)
  ams32.pos-valid       (bit OUT) - Flag: posicao salva e valida
  ams32.connected       (bit OUT) - Conexao ativa
  ams32.num-errors      (s32 OUT) - Contador de erros de comunicacao

Uso no HAL:
  loadusr -Wn ams32 python3 ams32_hal.py
"""

import hal
import time
import sys
import struct
import logging
import linuxcnc
from pymodbus.client import ModbusSerialClient
from pymodbus.framer import FramerType

# --- Logging ---
LOG_FILE = "/tmp/ams32_hal.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ams32")

# --- Config ---
SERIAL_PORT = "/dev/ttyAMS32"
BAUDRATE = 9600
SLAVE_ID = 1
POLL_RATE = 0.20  # 200ms = 5Hz (AMS32 precisa ~100ms entre requests)
POS_SAVE_INTERVAL = 2.0  # salvar posicao a cada 2 segundos
POS_VALID_MAGIC = 0xABCD  # valor magico para validar posicao salva

# Enderecos Modbus
ADDR_CMD       = 2148   # M100-M107 (escrita coils)
ADDR_STATUS    = 2248   # M200-M215 (leitura coils)
ADDR_FORCE_JOG = 2348   # M300-M303 (jog virtual: X+/X-/Z+/Z-)
ADDR_RPM       = 4196   # D100 (escrita registro)
ADDR_POS_X     = 6096   # D2000-D2001 (posicao X, float 32bit)
ADDR_POS_Z     = 6098   # D2002-D2003 (posicao Z, float 32bit)
ADDR_POS_OK    = 6100   # D2004 (flag validacao = 0xABCD)

NUM_CMD       = 8
NUM_STATUS    = 16
NUM_FORCE_JOG = 4


def float_to_regs(val):
    """Converte float para 2 registradores 16bit (big-endian)."""
    packed = struct.pack('>f', val)
    hi = (packed[0] << 8) | packed[1]
    lo = (packed[2] << 8) | packed[3]
    return [hi, lo]


def regs_to_float(hi, lo):
    """Converte 2 registradores 16bit para float (big-endian)."""
    packed = struct.pack('>HH', hi, lo)
    return struct.unpack('>f', packed)[0]


def main():
    log.info("=== ams32_hal iniciando ===")

    try:
        # Criar componente HAL
        h = hal.component("ams32")
        log.info("Componente HAL criado")

        # Pins de comando (LinuxCNC -> PLC)
        cmd_pins = []
        for i in range(NUM_CMD):
            h.newpin(f"cmd.{i:02d}", hal.HAL_BIT, hal.HAL_IN)
            cmd_pins.append(f"cmd.{i:02d}")

        # Pins de status (PLC -> LinuxCNC)
        status_pins = []
        for i in range(NUM_STATUS):
            h.newpin(f"status.{i:02d}", hal.HAL_BIT, hal.HAL_OUT)
            status_pins.append(f"status.{i:02d}")

        # Pins de force-jog (LinuxCNC -> M300-M303 = jog virtual)
        force_jog_pins = [
            "force-jog-x-pos", "force-jog-x-neg",
            "force-jog-z-pos", "force-jog-z-neg",
        ]
        for name in force_jog_pins:
            h.newpin(name, hal.HAL_BIT, hal.HAL_IN)

        # Pin RPM
        h.newpin("spindle-rpm", hal.HAL_FLOAT, hal.HAL_IN)

        # Contador de erros
        h.newpin("num-errors", hal.HAL_S32, hal.HAL_OUT)

        # Pin de conexao ativa
        h.newpin("connected", hal.HAL_BIT, hal.HAL_OUT)

        # Pins de posicao (save/restore)
        h.newpin("pos-cmd-x", hal.HAL_FLOAT, hal.HAL_IN)
        h.newpin("pos-cmd-z", hal.HAL_FLOAT, hal.HAL_IN)
        h.newpin("pos-saved-x", hal.HAL_FLOAT, hal.HAL_OUT)
        h.newpin("pos-saved-z", hal.HAL_FLOAT, hal.HAL_OUT)
        h.newpin("pos-valid", hal.HAL_BIT, hal.HAL_OUT)

        h.ready()
        log.info("Pins criados, componente ready")

    except Exception as e:
        log.exception("Erro criando componente HAL")
        sys.exit(1)

    # Conectar ao AMS32
    client = ModbusSerialClient(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        bytesize=7,
        parity="E",
        stopbits=1,
        framer=FramerType.ASCII,
        timeout=1,
        retries=1,
    )

    errors = 0
    connected = False
    last_cmd = [False] * NUM_CMD
    last_force_jog = [True] * NUM_FORCE_JOG  # forca escrita inicial para zerar M300-M303
    last_rpm = 0.0
    last_pos_save = 0.0
    pos_restored = False
    pos_applied = False
    stat = linuxcnc.stat()
    cmd = linuxcnc.command()

    log.info(f"Configurado: {SERIAL_PORT} ASCII 9600 7E1")
    print(f"ams32_hal: Iniciando em {SERIAL_PORT} ASCII 9600 7E1, log em {LOG_FILE}")

    try:
        while True:
            loop_start = time.monotonic()

            # Reconectar se necessario
            if not connected:
                try:
                    if client.connect():
                        connected = True
                        h["connected"] = True
                        log.info("Conectado ao AMS32")
                    else:
                        log.warning("Falha ao conectar, tentando em 1s")
                        time.sleep(1)
                        continue
                except Exception:
                    log.exception("Erro ao conectar")
                    time.sleep(1)
                    continue

            # --- 0. Restore posicao salva (1x no startup) ---
            if not pos_restored:
                try:
                    r = client.read_holding_registers(address=ADDR_POS_OK, count=1)
                    time.sleep(0.05)
                    if not r.isError() and r.registers[0] == POS_VALID_MAGIC:
                        r2 = client.read_holding_registers(address=ADDR_POS_X, count=4)
                        time.sleep(0.05)
                        if not r2.isError():
                            saved_x = regs_to_float(r2.registers[0], r2.registers[1])
                            saved_z = regs_to_float(r2.registers[2], r2.registers[3])
                            h["pos-saved-x"] = saved_x
                            h["pos-saved-z"] = saved_z
                            h["pos-valid"] = True
                            log.info(f"Posicao restaurada: X={saved_x:.4f} Z={saved_z:.4f}")
                            print(f"ams32_hal: Posicao salva encontrada: X={saved_x:.4f} Z={saved_z:.4f}")
                    else:
                        h["pos-valid"] = False
                        log.info("Nenhuma posicao salva valida no PLC")
                        print("ams32_hal: Nenhuma posicao salva no PLC")
                except Exception:
                    log.exception("Erro lendo posicao salva")
                pos_restored = True

            # --- 1. Ler status M200-M215 (PLC -> LinuxCNC) ---
            try:
                r = client.read_coils(address=ADDR_STATUS, count=NUM_STATUS)
                if not r.isError():
                    for i in range(NUM_STATUS):
                        h[status_pins[i]] = r.bits[i]
                else:
                    errors += 1
                    log.warning(f"Erro leitura status: {r}")
            except Exception:
                errors += 1
                log.exception("Excecao leitura status")
                connected = False
                h["connected"] = False
                client.close()
                continue

            time.sleep(0.05)  # pausa entre transacoes

            # --- 2. Escrever comandos M100-M107 (LinuxCNC -> PLC) ---
            # So escreve se algum valor mudou
            current_cmd = [h[cmd_pins[i]] for i in range(NUM_CMD)]
            if current_cmd != last_cmd:
                try:
                    r = client.write_coils(address=ADDR_CMD, values=current_cmd)
                    if not r.isError():
                        last_cmd = current_cmd[:]
                        log.info(f"Cmd escrito: {current_cmd}")
                    else:
                        errors += 1
                        log.warning(f"Erro escrita cmd: {r}")
                except Exception:
                    errors += 1
                    log.exception("Excecao escrita cmd")
                time.sleep(0.05)

            # --- 2b. Escrever force-jog M300-M303 se mudou ---
            current_fj = [h[p] for p in force_jog_pins]
            if current_fj != last_force_jog:
                try:
                    r = client.write_coils(address=ADDR_FORCE_JOG, values=current_fj)
                    if not r.isError():
                        last_force_jog = current_fj[:]
                        log.info(f"Force-jog escrito: {current_fj}")
                    else:
                        errors += 1
                        log.warning(f"Erro escrita force-jog: {r}")
                except Exception:
                    errors += 1
                    log.exception("Excecao escrita force-jog")
                time.sleep(0.05)

            # --- 3. Escrever RPM (D100) se mudou ---
            current_rpm = h["spindle-rpm"]
            if abs(current_rpm - last_rpm) > 0.5:
                try:
                    rpm_int = max(0, min(65535, int(current_rpm)))
                    r = client.write_register(address=ADDR_RPM, value=rpm_int)
                    if not r.isError():
                        last_rpm = current_rpm
                    else:
                        errors += 1
                except Exception:
                    errors += 1
                    log.exception("Excecao escrita RPM")

            # --- 4. Salvar posicao X/Z no PLC (a cada 2s, so se homed) ---
            now = time.monotonic()
            if now - last_pos_save >= POS_SAVE_INTERVAL:
                try:
                    stat.poll()
                    if stat.homed[0] and stat.homed[1]:
                        pos_x = h["pos-cmd-x"]
                        pos_z = h["pos-cmd-z"]
                        regs_x = float_to_regs(pos_x)
                        regs_z = float_to_regs(pos_z)
                        client.write_registers(address=ADDR_POS_X, values=regs_x + regs_z)
                        time.sleep(0.05)
                        client.write_register(address=ADDR_POS_OK, value=POS_VALID_MAGIC)
                        last_pos_save = now
                except Exception:
                    errors += 1
                    log.exception("Erro salvando posicao")

            # --- 5. Restaurar posicao salva apos home (DESATIVADO) ---
            # Estava sobrescrevendo G54 com a posicao de maquina salva, corrompendo
            # o zeramento da peca toda vez que se fazia Ref All. A logica original
            # (G10 L20 P1) muda o WCS, nao a posicao fisica da maquina.
            # Mantida a gravacao da posicao no PLC (bloco 4) caso seja util como log.
            # if not pos_applied:
            #     try:
            #         stat.poll()
            #         if stat.homed[0] and stat.homed[1]:
            #             if h["pos-valid"]:
            #                 saved_x = h["pos-saved-x"]
            #                 saved_z = h["pos-saved-z"]
            #                 cmd.mode(linuxcnc.MODE_MDI)
            #                 cmd.wait_complete()
            #                 cmd.mdi(f"G10 L20 P1 X{saved_x:.4f} Z{saved_z:.4f}")
            #                 cmd.wait_complete(5)
            #                 cmd.mode(linuxcnc.MODE_MANUAL)
            #                 cmd.wait_complete()
            #                 log.info(f"Posicao restaurada: X={saved_x:.4f} Z={saved_z:.4f}")
            #                 print(f"ams32_hal: Posicao restaurada! X={saved_x:.4f} Z={saved_z:.4f}")
            #             pos_applied = True
            #     except Exception:
            #         log.exception("Erro restaurando posicao")

            h["num-errors"] = errors

            # Manter taxa de polling
            elapsed = time.monotonic() - loop_start
            sleep_time = POLL_RATE - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except Exception as e:
        log.exception("Excecao no loop principal")
    finally:
        client.close()
        log.info("=== ams32_hal encerrado ===")
        print("ams32_hal: Encerrado")


if __name__ == "__main__":
    main()
