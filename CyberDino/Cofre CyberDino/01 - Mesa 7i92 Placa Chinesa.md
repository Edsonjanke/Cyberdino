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


## Nao ha entrada vaga utilizavel (medido em 2026-10-16)

Procuramos uma entrada livre pra por um botao de RODAR DA LINHA. **Nao
existe.**

O firmware deixa sete I/O fora dos modulos: **011, 012, 013, 028, 029,
032 e 033**. Todas aparecem como entrada, todas leem **0** em repouso — ou
seja, sem pull-up, ao contrario de 020..025 e 027, que leem 1 porque tem
botao ligado.

Encostando +5V nos pontos acessiveis, **nenhuma das 34 entradas reagiu**,
em tres tentativas. E o teste de controle no mesmo instante funcionou:
apertar o AUTO registrou na hora (GPIO.024).

Conclusao: o ponto nao chega no FPGA. E' o mesmo defeito ja' anotado aqui
— ponto soldado que nao esta ligado. A ferramenta e' `tools/acha_gpio.py`
(modo `--livres` lista os candidatos com direcao, valor em repouso e se
servem pra botao).

**Consequencia pro painel:** o GPIO.025 e' a unica entrada sobrando, e ela
ja' e' o MANUAL. O RODAR DA LINHA ficou **so' na tela** (decisao do
operador, 2026-10-16). O pino `dino_painel.rodar-linha` continua existindo
e testado no sim — se um dia aparecer uma entrada, e' so' descomentar as
duas linhas (`custom.hal` e `probe_basic_postgui_fix.hal`).

**Se for preciso um botao fisico novo:** nenhuma das sete tem pull-up,
entao botao ligado ao GND nao funciona nelas. Ou se poe pull-up externo
(~4k7 pro +5V) e usa `.in_not`, ou se liga o botao no +5V e usa `.in`
direto — com pull-down externo pra nao ficar flutuando.
