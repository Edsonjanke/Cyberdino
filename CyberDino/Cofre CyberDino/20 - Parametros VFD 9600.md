# Parametros VFD 9600 - Configuracao Atual

**Ultima atualizacao:** 2026-04-23 (primeira parametrizacao completa apos retrofit)

## Grupo P0 - Basicos

| Param | Valor | Descricao |
|---|---|---|
| P0-00 | 0 | G type (torque constante) |
| P0-01 | 0 | SVC (sensorless vector control) |
| P0-02 | 1 | Command source = terminal (X1/X2) |
| P0-03 | 2 | Main freq source = AI1 (0-10V) |
| P0-10 | 60.00 | Max frequency (Hz) |
| P0-12 | 60.00 | Upper limit frequency (Hz) |
| P0-15 | 2.0 | Carrier frequency (kHz) — baixo para reduzir EMI |
| P0-17 | 10.0 | Accel time (s) |
| P0-18 | 10.0 | Decel time (s) |
| P0-28 | 0 | Comm protocol = Modbus RTU |

## Grupo P1 - Motor

| Param | Valor | Descricao |
|---|---|---|
| P1-00 | 1 | Common asynchronous motor |
| P1-01 | 7.5 | Potencia (kW) |
| P1-02 | 380 | Tensao (V) |
| P1-03 | 12.0 | Corrente (A) |
| P1-04 | 60.00 | Frequencia (Hz) |
| P1-05 | 1750 | RPM nominal |
| P1-37 | 2 | Auto-tuning estatico (executado 2026-04-23) |

Apos P1-37=2 + RUN no painel, os seguintes sao preenchidos automaticamente:
- P1-06 Stator resistance
- P1-07 Rotor resistance
- P1-08 Leakage inductance
- P1-09 Mutual inductance
- P1-10 No-load current

## Grupo P4 - Entradas Digitais

| Param | Valor | Descricao |
|---|---|---|
| P4-00 | 1 | X1 = Forward run (FWD) |
| P4-01 | 2 | X2 = Reverse run (REV) |
| P4-11 | 0 | Two-line mode 1 (X1 e X2 mutuamente exclusivos) |
| P4-33 | 321 | AI curve selection (default, curve 1 para AI1) |

## Grupo P4 - AI1 Curve (default, conferido)

| Param | Valor | Descricao |
|---|---|---|
| P4-13 | 0.00 | Min input voltage (V) |
| P4-14 | 0.0 | Corresponding % min |
| P4-15 | 10.00 | Max input voltage (V) |
| P4-16 | 100.0 | Corresponding % max (100% de P0-10 = 60Hz) |

## Grupo P6 - Start/Stop + Freio

| Param | Valor | Descricao |
|---|---|---|
| P6-10 | 0 | Decelerate to stop (default) |
| P6-15 | 100 | Brake use ratio (%) — usa resistor 100% do tempo |

## Grupo PP - Protecao

| Param | Valor | Descricao |
|---|---|---|
| PP-00 | 0 | Sem senha de usuario |
| PP-03 | 00 | Desabilita modos QUICK para nao trocar display |
| PP-04 | 0 | Parametros modificaveis |

## Grupo A5 - Controle (opcional se EMI/ressonancia)

| Param | Valor | Descricao |
|---|---|---|
| A5-03 | 0 | Random PWM depth (0=invalid, 1-10 = spread ruido) |
| A5-09 | 810.0 | Overvoltage threshold (default 380V class) |

## Monitoramento (Grupo U0)

Para ler via display ou Modbus:
- U0-00 Running frequency (0x7000)
- U0-03 Output voltage
- U0-04 Output current (load spindle)
- U0-05 Output power
- U0-06 Output torque %
- U0-07 X state (bitmap das entradas)
- U0-14 Load speed
- U0-21 AI1 voltage before correction (diagnostico)

## Reset de fabrica
```
PP-01 = 1       restaura defaults (volta a 0 sozinho)
```
**ATENCAO:** reset apaga tambem parametros de motor, precisa redigitar P1-00 a P1-05 e rodar P1-37=2 novamente.

---

## Ver tambem
- [[03 - Inversor VFD 9600]]
- [[11 - HAL Spindle VFD 9600]]
