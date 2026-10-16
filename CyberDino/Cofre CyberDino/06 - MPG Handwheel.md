# MPG Handwheel — um volante por eixo

**Mudou em 2026-10-16:** a chave que escolhia o eixo saiu. Agora sao
**dois volantes**, um pra cada eixo, e os dois ficam armados juntos — quem
escolhe o eixo e' a mao do operador.

## Hardware
- Encoder diferencial (A/B/-A/-B), so' A/B ligados
- Software encoder no LinuxCNC (`loadrt encoder num_chan=2` no custom.hal):
  `encoder.0` = volante do X, `encoder.1` = volante do Z
- Escala: vem do widget JogIncrement (0.01 / 0.1 / 1 mm por click)
- `x4-mode 0`: 1 count por detente, nao 4 — assim 1 clique anda exatamente
  o incremento escolhido

## Pinagem

| GPIO | I/O | Funcao | Onde |
|------|-----|--------|------|
| GPIO.030 | IN | Volante do X - fase A | DB15 pino 10 |
| GPIO.031 | IN | Volante do X - fase B | DB15 pino 7 |
| GPIO.016 | IN | Volante do Z - fase A | P2 pino 13 |
| GPIO.026 | IN | Volante do Z - fase B | P1 pino 6 |
| GPIO.027 | IN | Botao MPG (pulso) | arma/desarma os dois |

## Botao MPG (era chave de manter)

Virou botao momentaneo. O componente `toggle` guarda o estado. Esse estado
e' so' nosso — nao existe em lugar nenhum do LinuxCNC — entao ele nunca
desencontra de nada (diferente dos botoes de modo e do refrigerante, ver
[[07 - Botoes de Modo e Refrigerante]]).

```
GPIO.027 -> toggle.mpg -> mpg-enabled -> joint.0/1.jog-enable
                                      -> axis.x/z.jog-enable
```

Os sinais `axis-select-x` / `axis-select-z` sao do tempo da chave de eixo e
ficaram **sem ninguem escrevendo** (valem FALSE). Eles so' alimentam
`halui.axis.x/z.select`, que serve pro `halui.axis.selected.plus/minus` —
e isso ninguem usa aqui: os botoes de jog do PLC vao direto em
`halui.axis.x.plus` / `.minus`.

## Funcao dupla em AUTO

| volante | em AUTO | fora do AUTO |
|---|---|---|
| X | **feed override** (1% por click) | jog do X |
| Z | **rapid override** (1% por click) | jog do Z |

Trocado em 2026-10-16 a pedido do operador: na primeira versao era o
contrario (X no rapid, Z no feed).

**O volante do Z sempre esteve no GPIO.016/026.** Era ele que mexia no
feed override antes da reforma — o comentario antigo do `custom.hal`
chamava esse par de "encoder FYSETC EC11", como se fosse um botaozinho
separado, e nao era. O que mudou em 2026-10-16: alem do feed override ele
passou a fazer jog do Z, e o feed override passou a valer so' em AUTO.

A troca de funcao e' feita pelo `count-enable` ligado em
`halui.mode.is-auto`. **Medido no sim:** girar o volante fora do AUTO nao
mexe no override, e voltar pro AUTO **nao da' salto** — o halui acompanha
as contagens mesmo com o count-enable desligado, entao nao acumula o que
foi girado em jog. Dentro do AUTO cada click e' exatamente 1%.

## Interface ProbeBasic
- Widget `MpgButton` em `mpg_button.py` (indicador visual read-only)
- Pin HAL: `qtpyvcp.mpg-indicator.in`
- Conexao: `net mpg-enabled => qtpyvcp.mpg-indicator.in`

## Status
Um volante desde 2026-04-06; dois volantes desde 2026-10-16.
**Os dois volantes nao foram testados na maquina ainda.**
