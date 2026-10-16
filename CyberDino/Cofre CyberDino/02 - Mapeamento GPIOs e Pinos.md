# Mapeamento GPIOs e Pinos

## DB15 (P1) - Confirmado por teste

| Pino DB15 | I/O | GPIO/Funcao | Uso |
|-----------|-----|-------------|-----|
| 3 | 18 | encoder.00.B | Encoder spindle fase B |
| 4 | 17 | encoder.00.A | Encoder spindle fase A |
| 7 | 31 | GPIO.031 | MPG encoder fase B |
| 10 | 30 | GPIO.030 | MPG encoder fase A |
| 14 | - | GND | Terra |
| 15 | - | +5V | Alimentacao |

## GPIOs Usados (via DB15 / pontos soldados)

| GPIO | I/O | Funcao | Notas |
|------|-----|--------|-------|
| GPIO.020 | IN | Botao CYCLE START | pulso |
| GPIO.021 | IN | Botao PAUSE | pulso |
| GPIO.022 | IN | Botao RESET | pulso (estop clear + liga maquina) |
| GPIO.023 | IN | Botao REFRIGERANTE | pulso, alterna liga/desliga |
| GPIO.024 | IN | Botao AUTO | pulso |
| GPIO.025 | IN | Botao MANUAL | pulso (abre o EDITAR junto) |
| GPIO.027 | IN | Botao MPG | pulso, arma/desarma os dois volantes |
| GPIO.028 | IN | Volante do Z - fase A | P1 pino 8 |
| GPIO.029 | IN | Volante do Z - fase B | P1 pino 9 |
| GPIO.030 | IN | Volante do X - fase A | DB15 pino 10 |
| GPIO.031 | IN | Volante do X - fase B | DB15 pino 7 |

Painel refeito em **2026-10-16**: sairam a chave seletora de modo
(024/023), a chave de eixo do MPG (025), a chave de enable do MPG (027) e
o encoder de feed override (016/026). No lugar, so' botoes de pulso e um
volante por eixo.

**GPIOs livres hoje: 016, 026, 032 e 033** (P1 pinos 12 e 13 para os dois
ultimos). Conferido com
`mesaflash --device 7i92 --addr 10.10.10.10 --readhmid`.

## DB25 (P2) - Step/Dir + PWM

| Pino P2 | Funcao | Uso |
|---------|--------|-----|
| Step/Dir X | stepgen.00 | Eixo X |
| Step/Dir Z | stepgen.01 | Eixo Z |
| P2-12 | GPIO.015 | E-Stop (NF) |
| P2-14 | pwmgen.01 | PWM1 -> Rele Enable CFW-07 |
| P2-15 | pwmgen.02 | PWM2 -> Rele Direcao CFW-07 |
