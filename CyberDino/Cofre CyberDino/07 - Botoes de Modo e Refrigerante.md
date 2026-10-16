# Botao de Modo (pulso) — antes era chave seletora

**Mudou em 2026-10-16:** o painel de operacao foi refeito. A chave
seletora de 3 posicoes saiu; no lugar ficou um **botao de pulso**, e a
entrada que era do MDI virou o **liga/desliga do refrigerante**.

## Como e' hoje

| GPIO | Funcao | O que faz |
|---|---|---|
| GPIO.024 | Botao de MODO (momentaneo) | cada toque alterna AUTO <-> MANUAL |
| GPIO.023 | Botao do REFRIGERANTE (momentaneo) | cada toque liga/desliga a bomba |

Nao ha mais botao fisico de MDI. O MDI continua na tela — digitar na caixa
MDI ja troca o modo sozinho.

O componente `toggle` transforma o toque momentaneo num NIVEL que fica ate
o proximo toque. Esse nivel faz exatamente o papel que a posicao da chave
fazia, entao o resto do `custom.hal` nao precisou mudar.

```
GPIO.024 -> and2 (programa parado?) -> toggle.modo -> halui.mode.auto
                                              \-> NOT -> halui.mode.manual
GPIO.023 -> and2 (maquina ligada?)  -> toggle.refrig -> halui.flood.on
                                              \-> NOT -> halui.flood.off
```

Debounce de 30 ms (`setp toggle.*.debounce 30`, servo-thread de 1 ms).

## O toque e' ignorado com programa rodando ou pausado

Decisao do operador (2026-10-16): um esbarrao no botao nao pode derrubar o
ciclo. Para parar, PAUSA no painel ou PARAR na tela.

O bloqueio e' na **entrada** do toggle, nao na saida — senao o pedido
ficaria represado e dispararia sozinho no instante em que o programa
acabasse.

Com isso o **interlock antigo deixou de existir**. Ele parava o programa
quando a chave saia do AUTO; sem chave nao ha "posicao fora do AUTO" pra
detectar, e com a entrada bloqueada o nivel nem muda durante o ciclo.
O que sobrou do tempo da chave: o Cycle Start fisico continua so' valendo
em AUTO, mas agora olhando `halui.mode.is-auto` (o modo de verdade) em vez
do nivel do botao.

## Armadilha paga: o toggle2nist NAO serve pra botao momentaneo

O caminho "obvio" seria o `toggle2nist`, que leria o estado real
(`halui.mode.is-auto`, `halui.flood.is-on`) e nunca desencontraria. O man
page dele diz, com desenho e tudo, que a saida muda na borda de SUBIDA.

**Medido na bancada (halrun, componente sozinho): ele alterna nas DUAS
bordas.** Apertar e soltar da' dois comandos, que se anulam — o botao
ficaria morto.

| passo | in | is-on | on | off |
|---|---|---|---|---|
| aperta | 1 | 0 | **TRUE** | FALSE |
| ligou (ainda apertado) | 1 | 1 | FALSE | FALSE |
| **solta** | 0 | 1 | FALSE | **TRUE** |

Ou seja, o `in` dele e' pra ser um NIVEL, nao um botao. E, por perseguir o
estado, ele tambem brigaria com o M8/M9 do programa e com os botoes da
tela: com o nivel em "desligado" e a bomba ligada pelo G-code, ele
desligaria a bomba sozinho.

## Por que segurar um nivel em TRUE nao prende nada

O desenho deixa `halui.mode.manual` (ou `halui.flood.off`) em TRUE o tempo
todo enquanto o botao esta' no outro estado. Isso so' e' seguro porque o
**halui atende esses pinos por BORDA**. Medido no sim:

| teste | resultado |
|---|---|
| `flood.off` preso em TRUE, depois pulso no `flood.on` | bomba LIGA (M8 do programa nao e' atrapalhado) |
| `mode.manual` preso em TRUE, depois pulso no `mode.auto` | entra em AUTO |
| `mode.manual` preso em TRUE, tela pede MDI | entra em MDI |

## Preco do desenho: um toque perdido

Como o nivel nao le o estado real, se o modo (ou a bomba) for trocado por
fora — INICIAR na tela forca AUTO via NML, o G-code liga a bomba com M8 —
o nivel fica desencontrado e o **primeiro toque seguinte vira no-op**; o
segundo ja acerta. Nao trava nada e nao briga com ninguem.

## Interface ProbeBasic

Os botoes MAN/AUTO/MDI da tela sao `ReadOnlyAction` (widget em
`mpg_button.py`): **so' indicador, nao clicaveis**. Era assim porque quem
mandava era a chave fisica.

**Pendente de decisao:** com a chave fora e sem botao fisico de MDI, o
unico caminho pro modo MDI e' digitar na caixa MDI. Se incomodar, da' pra
voltar o `mdi_mode_button` a ser clicavel.

## Teste

`custom.hal` nao sobe no sim (o sim usa `custom_sim.hal`). A logica foi
conferida numa bancada do `halrun` que repete o circuito com as entradas
soltas — 28 passos, incluindo aperta/solta de verdade, toque durante
programa rodando e pausado, e maquina desligada. Ver
[[23 - Erros e Solucoes]].

## Status

Em uso desde 2026-04-06 como chave seletora; virou botao de pulso em
2026-10-16. **Nao testado na maquina ainda.**
