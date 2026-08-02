# PLC AMS32ES2

## Status: FUNCIONANDO - Modbus ASCII via COM1 RS-232 (2026-04-15)

## Especificacoes
- Clone Delta DVP-32ES200R
- 16 DI / 16 DO
- Comunicacao Modbus ASCII via COM1 RS-232

## Comunicacao
| Porta | Tipo | Protocolo | Uso |
|-------|------|-----------|-----|
| COM1 (Mini-DIN) | RS-232 | Modbus ASCII escravo | **FUNCIONANDO** (Ladder configura D1036=H87, M1139=OFF) |
| COM2/COM3 (terminais D+/D-/SG) | RS-485 | Modbus RTU | Nao usado (adaptador USB-RS485 defeituoso) |

## Componente HAL
- `ams32_hal.py` - Python3 + pymodbus 3.12 (FramerType.ASCII)
- Porta: `/dev/ttyAMS32` (udev rule, CH340)
- 9600 bps, 7 data, Even parity, 1 stop
- POLL_RATE: 200ms, pausa 50ms entre transacoes

## Pins HAL
| Pin | Tipo | Direcao | Funcao |
|-----|------|---------|--------|
| ams32.cmd.00-07 | bit | IN | Comandos LinuxCNC -> PLC (M100-M107) |
| ams32.status.00-15 | bit | OUT | Status PLC -> LinuxCNC (M200-M215) |
| ams32.spindle-rpm | float | IN | RPM para PLC (D100) |
| ams32.pos-cmd-x/z | float | IN | Posicao atual (salva no PLC a cada 2s) |
| ams32.pos-saved-x/z | float | OUT | Posicao salva (lida no startup) |
| ams32.pos-valid | bit | OUT | Flag posicao salva valida |
| ams32.connected | bit | OUT | Conexao ativa |

## Position Save/Restore
- D2000-D2001 = posicao X (float 32bit, retentivo)
- D2002-D2003 = posicao Z (float 32bit, retentivo)
- D2004 = flag validacao (0xABCD)
- `pos_restore.py` - home automatico + G10 L20 no startup
- Elimina necessidade de home manual ao religar

## Ladder (WPLSoft IL)
| Bloco | Funcao |
|-------|--------|
| 0 | Init: COM1 Modbus escravo, lube defaults |
| 1 | Coolant: M100 -> Y0 (com bloqueio por alarme) |
| 2 | Spindle: M101+M102 -> Y1/Y2 (FWD/REV) |
| 4 | Jog: X0-X3 -> M200-M203 (debounce 100ms) |
| 5 | Alarme coolant: X5 -> M205 + Y4 buzzer |
| 6 | Alarme lube: X6 -> M206 |
| 7 | Falha geral: X7 -> M207 (bloqueia tudo) |
| 8 | Lube temporizada: M103 -> Y3 (D110/D111 config) |
| 9 | Alarme servo X: /X10 -> M210 + M207 + Y4 (X OFF = opto cortou) |
| 10 | Alarme servo Z: /X11 -> M211 + M207 + Y4 |

## Mapa de X (entradas) atualizado
| X | Funcao |
|---|--------|
| X0-X3 | Jog (X+/X-/Z+/Z-) |
| X4 | livre |
| X5 | Alarme coolant |
| X6 | Alarme lube |
| X7 | Falha geral externa |
| X10 | **Alarme servo X** (ALM- HLTNC T3D, opto conduz = OK) |
| X11 | **Alarme servo Z** (ALM- HLTNC T3D) |
| X12-X17 | livre |

## Funcoes Planejadas
- Encoder FYSETC (EC11) -> PLC X0/X1 -> feed override
- Botoes jog X+/X-/Z+/Z- via PLC
- Display FYSETC Mini 12864 (SPI) -> feed override %

## Hardware Descartado
- BTT Octopus (impressora 3D) - nao adequado
- Adaptador USB-RS485 - defeituoso (nao e RS-485 real)
