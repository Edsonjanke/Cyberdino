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
| GPIO.028 | IN | Botao RODAR DA LINHA | pulso — **pino a conferir** |
| GPIO.016 | IN | Volante do Z - fase A | P2 pino 13 |
| GPIO.026 | IN | Volante do Z - fase B | P1 pino 6 |
| GPIO.030 | IN | Volante do X - fase A | DB15 pino 10 |
| GPIO.031 | IN | Volante do X - fase B | DB15 pino 7 |

Painel refeito em **2026-10-16**: sairam a chave seletora de modo
(024/023), a chave de eixo do MPG (025) e a chave de enable do MPG (027).
No lugar, so' botoes de pulso e um volante por eixo.

O par **016/026 sempre foi o volante do Z** — era o que mexia no feed
override. O `custom.hal` antigo chamava de "encoder FYSETC EC11", como se
fosse um botaozinho a parte, e isso ja' custou uma viagem a' maquina: o
volante foi remapeado pra 028/029, onde nao ha fio nenhum, e ficou mudo.

**GPIOs livres hoje: 029, 032 e 033** (P1 pinos 9, 12 e 13) — a 028
ficou com o RODAR DA LINHA, ainda por confirmar na maquina.
Conferido com `mesaflash --device 7i92 --addr 10.10.10.10 --readhmid`.

Na duvida sobre em que pino esta alguma coisa, **nao deduza**: com o
LinuxCNC rodando, `python3 tools/acha_gpio.py` mostra quais entradas mudam
enquanto voce aperta o botao ou gira o volante.

## DB25 (P2) - Step/Dir + PWM

| Pino P2 | Funcao | Uso |
|---------|--------|-----|
| Step/Dir X | stepgen.00 | Eixo X |
| Step/Dir Z | stepgen.01 | Eixo Z |
| P2-12 | GPIO.015 | E-Stop (NF) |
| P2-14 | pwmgen.01 | PWM1 -> Rele Enable CFW-07 |
| P2-15 | pwmgen.02 | PWM2 -> Rele Direcao CFW-07 |
