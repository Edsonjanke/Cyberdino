# Mesa 7i92 - Placa Chinesa Integrada

## Descricao
Placa chinesa que integra Mesa 7i92 + BOB (Breakout Board) na mesma PCB.
Firmware: `7i92_5ABOB_Enc.bit`

## Capacidades do Firmware
- 1 encoder hardware
- 3 PWM generators (com saida 0-10V analogica nos terminais)
- 5 step generators
- GPIOs restantes

## Configuracao no HAL
```
loadrt hm2_eth board_ip="10.10.10.10" config="num_encoders=1 num_pwmgens=3 num_stepgens=5"
setp hm2_7i92.0.pwmgen.pwm_frequency 500
```

## Conexao
- IP fixo: 10.10.10.10
- Ethernet direto PC <-> placa

## Limitacoes Conhecidas
- **P2 (DB25)**: optoacopladores unidirecionais - pinos step/dir so funcionam como SAIDA
- **Pontos soldados na placa para GPIOs podem NAO estar conectados ao FPGA** (conectores mortos)
- **Sempre testar GPIO com halcmd antes de confiar no mapeamento**
- Max 1 encoder hardware (sem Index Z disponivel)

## PWM Outputs (Terminais na placa)
Os terminais PWM da placa possuem capacitores de filtro que convertem PWM em **0-10V analogico**.

| PWM | Funcao Atual | Pino P2 |
|-----|-------------|---------|
| PWM0 | Velocidade spindle (0-10V) | - |
| PWM1 | Enable spindle (rele -> DI1 CFW-07) | P2-14 |
| PWM2 | Direcao CCW (rele -> DI2 CFW-07) | P2-15 |

## Alimentacao
- 24V externo para logica e reles

## Fotos
![[引脚定义.jpg]]
