# Inversor VFD 9600 (nFlixin CNWeiken)

**Substituto do CFW-07 queimado em 2026-04-17.** Instalado 2026-04-23.

## Especificacoes
- **Modelo:** 9600-3T-00075-G
- **Tipo:** Vetorial sensorless (SVC), embedded braking unit
- **Entrada:** 3PH 380V 50/60Hz
- **Saida:** 3PH 0-380V 0-650Hz
- **Potencia:** 7.5 kW (10 HP)
- **Corrente nominal:** ~18A
- **Fabricante:** Shenzhen NFlixin Technology (CNWeiken)
- **Manual:** `/home/evo/Área de trabalho/Dino_Evo/CyberDino/spindle motor e inversor/S35e23cd849024e73936149f689c7d1e0n.pdf`

## Topologia de Controle (Two-line Mode 1)

X1 e X2 sao mutuamente exclusivos (nao usa "enable + direction" como CFW-07):

| Comando LinuxCNC | Rele 1 (X1) | Rele 2 (X2) | Efeito |
|---|---|---|---|
| M3 (FWD) | ON | OFF | Roda horario |
| M4 (REV) | OFF | ON | Roda anti-horario |
| M5 (STOP) | OFF | OFF | Para (rampa P0-18) |

## Fiacao

### Potencia
- R/S/T: entrada trifasica 380V
- U/V/W: saida para motor
- PE: terra do motor volta pelo cabo do motor ao PE do VFD (nao direto no quadro)
- P+/PB: resistor de frenagem 60Ω 900W (3x 20Ω/300W em serie)

### Controle
- X1 (FWD): Rele 1 da BOB Mesa (pwmgen.01 como digital)
- X2 (REV): Rele 2 da BOB Mesa (pwmgen.02 como digital)
- DCOM: comum dos reles
- AI1: sinal 0-10V da BOB Mesa (pwmgen.00 + filtro RC)
- GND/ACOM: GND analogico da BOB Mesa
- Jumper OP-+24V: fechado (default)
- Jumper AI1: posicao 0-10V (upper)

## Resistor de Frenagem
- 3x 20Ω 300W wirewound verde em serie = 60Ω 900W
- Conectado em P+/PB (sem polaridade)
- Montado em caixa ventilada separada
- P6-15 = 100 (brake use ratio 100%)

## Modbus RTU (planejado, nao cabeado ainda)
- A/B terminais RS-485 no VFD
- COM2 do AMS32 OU adaptador USB-RS485 no PC
- Registros monitoramento (0x7000-0x7044):
  - U0-00 (0x7000) freq atual
  - U0-03 V out
  - U0-04 corrente (ler load do spindle)
  - U0-05 power
  - U0-06 torque %
  - U0-14 load speed
- Registros controle (escrita):
  - 0x1000: set frequency
  - 0x2000: comando (1=FWD, 2=REV, 5=STOP, 7=RESET)
- Parametros diretos: P0-xx = 0x00xx, P1-xx = 0x01xx, etc.

## Licoes Aprendidas

### Senha PP-00
Pode travar acidentalmente em "1" (cinco zeros piscando = prompt de senha).
Desbloqueio: digitar a senha e ENTER. Para evitar: **sempre PP-00 = 0** durante config.

### Tecla QUICK e PP-03
A tecla QUICK cicla entre tres modos de display: `-bASE` (tudo), `-USEr` (so user-defined do PE), `--C--` (so modificados). Se apertar sem querer, caiu em modo com poucos parametros visiveis.
Fix: apertar QUICK ate voltar ao `-bASE`. Ou `PP-03 = 00` para desabilitar.

### Jumper J9 / AI1
Em modelos 0.75-4KW tem J9 (pot painel vs AI1 externo). Em 4-630KW (este) tem jumpers V/I para cada AI (0-10V upper ou 4-20mA lower).

### EMI com portadora alta
P0-15 alto (>5 kHz) desligava monitor do PC por EMI radiada. Solucao: P0-15 = 2.0 kHz + distanciar cabos do motor dos cabos de sinal.

### Parametros bloqueados por limite
P1-04 (freq motor) nao aceita 60 se P0-10 (max freq) estiver em 50 (default chines).
**Ordem correta:** grava P0-10 e P0-12 = 60 ANTES de P1-04.

### Auto-tuning estatico
Motor acoplado ao torno, nao da para desacoplar. Usa P1-37=2 (static). Nao gira, so mede R/L. ~30-60s. Apos termina, volta para 0 sozinho.

### Escala de voltagem PWM->VFD
BOB da Mesa chinesa produz 2x voltagem esperada no filtro RC. Compensado com `pwmgen.00.scale = 2975` (ao inves de 1700 teorico). Calibrado empiricamente: cmd S1200 -> real 1200.

---

## Ver tambem
- [[11 - HAL Spindle VFD 9600]]
- [[20 - Parametros VFD 9600]]
- [[22 - Fiacao Completa]]
