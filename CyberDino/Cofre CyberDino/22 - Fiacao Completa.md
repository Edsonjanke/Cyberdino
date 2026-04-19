# Fiacao Completa - CyberDino

## Spindle (Mesa -> CFW-07)

```
PLACA MESA/BOB              RELES NA (24V)           CFW-07 (XC1)
==============              ==============           =============

PWM0 (0-10V analog) ────── direto ──────────────── AI1+ (borne 02) velocidade
GND placa ──────────────── direto ──────────────── AGND (borne 04)

PWM1 (24V rele coil) ───── Rele 1 NA ──┐
                           fecha ───────┤── 0V ─── DI1 (borne 09) enable
                                        └───────── 0V  (borne 08)

PWM2 (24V rele coil) ───── Rele 2 NA ──┐
                           fecha ───────┤── 0V ─── DI2 (borne 10) direcao
                                        └───────── 0V  (borne 08)

Jumper fixo: ────────────────────────── 0V ──────── DI4 (borne 12) rampa
                                        └───────── 0V  (borne 08)
```

## Potencia (CFW-07 -> Motor)

```
Rede 380V 3~ ──── Disjuntor ──── R(1), S(2), T(3) do X1
                                  U(5), V(6), W(7) ──── Motor 7.5CV
                                  PE ──── Terra protecao
```

## Resistor de Frenagem (MR-RB51-T -> CFW-07)

```
MR-RB51-T                       CFW-07 (X1)
===========                      ===========
C ──────────── cabo trancado ──── BR  (borne 8)
P ──────────── cabo trancado ──── +Ud (borne 9)
```

## E-Stop

```
GPIO.015 (P2-12, NF) ──── and2.estop ──── user-enable-out
                          (configurado no custom.hal)
```

## Encoder Spindle (DB15)

```
DB15 pino 4 ──── I/O 17 ──── encoder.00.A
DB15 pino 3 ──── I/O 18 ──── encoder.00.B
DB15 pino 14 ──── GND
```

## MPG Handwheel (DB15 + pontos soldados)

```
DB15 pino 10 ──── I/O 30 ──── GPIO.030 ──── MPG fase A
DB15 pino 7  ──── I/O 31 ──── GPIO.031 ──── MPG fase B
Ponto soldado ──── GPIO.027 ──── Chave Enable
Ponto soldado ──── GPIO.025 ──── Chave X/Z
```

## Chave Seletora Modo (pontos soldados)

```
Ponto soldado ──── GPIO.024 ──── Chave AUTO (GND = AUTO)
Ponto soldado ──── GPIO.023 ──── Chave MDI  (GND = MDI)
Ambos soltos = JOG
```

## Painel Secundario (Pi 3B+)

```
PC (192.168.0.120) ──── Cabo ──── Pi (192.168.0.103)
                   VNC porta 5901
```
