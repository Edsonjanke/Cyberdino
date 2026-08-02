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
| GPIO.023 | IN | Chave seletora MDI | GND = MDI |
| GPIO.024 | IN | Chave seletora AUTO | GND = AUTO |
| GPIO.025 | IN | Chave MPG X/Z | OFF=X, ON=Z |
| GPIO.027 | IN | Chave MPG enable | Liga/desliga MPG |
| GPIO.030 | IN | MPG encoder fase A | DB15 pino 10 |
| GPIO.031 | IN | MPG encoder fase B | DB15 pino 7 |

## DB25 (P2) - Step/Dir + PWM

| Pino P2 | Funcao | Uso |
|---------|--------|-----|
| Step/Dir X | stepgen.00 | Eixo X |
| Step/Dir Z | stepgen.01 | Eixo Z |
| P2-12 | GPIO.015 | E-Stop (NF) |
| P2-14 | pwmgen.01 | PWM1 -> Rele Enable CFW-07 |
| P2-15 | pwmgen.02 | PWM2 -> Rele Direcao CFW-07 |
