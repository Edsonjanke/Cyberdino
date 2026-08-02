# Inversor WEG CFW-07

## Dados da Plaqueta
| Dado | Valor |
|------|-------|
| **Modelo** | CFW07016T3848PSZ |
| **Rede** | 380...480VAC 50/60Hz |
| **Saida** | 0...300Hz, 16A |
| **Serial** | MXA09128SSA012 |
| **Potencia** | 10 CV |
| **Tipo** | IGBT, controle U/F, PWM SVM |

## Conector de Controle XC1

### Parte Analogica
| Borne | Funcao | Conexao |
|-------|--------|---------|
| 01 | +10V fonte interna | Nao usado |
| 02 | AI1+ (CW) | **PWM0 da Mesa (0-10V) = velocidade** |
| 03 | AI1- (CCW) | Nao usado |
| 04 | 0V (AGND) | **GND da Mesa** |
| 07 | AO1 saida analogica | Opcional (freq saida) |

### Parte Digital
| Borne | Funcao | Conexao |
|-------|--------|---------|
| 08 | 0V (DGND) | **Comum dos reles** |
| 09 | DI1 - Habilita Geral | **Rele 1 (PWM1) -> 0V** |
| 10 | DI2 - Sentido Giro | **Rele 2 (PWM2) -> 0V** |
| 11 | DI3 - Local/Remoto | Nao usado (P220=1) |
| 12 | DI4 - Habilita Rampa | **Jumper fixo -> 0V (borne 08)** |
| 13-14 | RL1 (NA/C) | Fs>Fx (opcional) |
| 15-16 | RL2 (NA/C) | Sem erro (opcional) |

### Entradas Digitais
- Tipo **NPN**: ativam com 0V (< 0.5V), inativas com >5V
- Pull-up interno a +12V via 6K8 ohm
- Corrente: ~12mA

## Conector de Potencia X1
| Borne | Funcao |
|-------|--------|
| R, S, T | Entrada 380V trifasica |
| U, V, W | Saida motor trifasico |
| PE | Terra de protecao |
| BR (8) | Resistor de frenagem (-) |
| +Ud (9) | Resistor de frenagem (+) / barramento DC |

## Resistor de Frenagem

| Dado | Valor |
|------|-------|
| **Modelo** | MR-RB51-T (Ling-Yang Precision) |
| **Tipo** | 3x resistores ceramicos (fio) |
| **Conexao** | C → BR (borne 8), P → +Ud (borne 9) |
| **Min. requerido** | 50W (Tabela 3.3 manual, 16/3AC.380-480) |

**Funcao:** Dissipa energia regenerativa durante desaceleracao do motor.
Sem resistor, tensao DC sobe e causa erro **E01** (sobretensao).

**Parametros frenagem:**
- P101 = 2.0s (rampa desaceleracao rapida)
- P300 = 1.5s (frenagem CC no final)
- P301 = 1.0Hz (freq inicio CC)
- P302 = 4.0% (tensao CC)

**Cuidados:**
- Cabo trancado entre inversor e resistor
- Separar dos cabos de sinal/controle
- Montar em local ventilado (alta temperatura)
- Se der E01 na desaceleracao, aumentar P101 para 2.5s ou 3.0s

## Logica de Controle

```
M3 (CW):  PWM0 = velocidade, PWM1 ON (rele DI1=0V=habilitado), PWM2 OFF (DI2=aberto=horario)
M4 (CCW): PWM0 = velocidade, PWM1 ON (rele DI1=0V=habilitado), PWM2 ON (rele DI2=0V=anti-horario)
M5 (STOP): PWM0 = 0V, PWM1 OFF (rele DI1=aberto=desabilitado), PWM2 OFF
```

## Ver tambem
- [[04 - Motor Spindle]]
- [[11 - HAL Spindle CFW-07]]
- [[20 - Parametros CFW-07]]
- [[21 - Pinout Conector XC1]]
- [[22 - Fiacao Completa]]
