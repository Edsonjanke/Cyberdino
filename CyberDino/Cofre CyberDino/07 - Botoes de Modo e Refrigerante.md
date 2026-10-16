# Botoes de Modo e Refrigerante — antes era chave seletora

**Mudou em 2026-10-16:** o painel de operacao foi refeito. A chave
seletora de 3 posicoes saiu; no lugar ficaram **botoes de pulso** — um pra
AUTO, um pra MANUAL — e a entrada que era do MDI virou o **liga/desliga do
refrigerante**. Ver tambem [[06 - MPG Handwheel]], que mudou junto.

## Como e' hoje

| GPIO | Botao | O que faz |
|---|---|---|
| GPIO.024 | AUTO | entra em modo AUTO |
| GPIO.025 | MANUAL | entra em MANUAL **e abre o EDITAR na tela** |
| GPIO.023 | REFRIGERANTE | alterna liga/desliga a bomba |
(o RODAR DA LINHA ficou **so' na tela** — nao sobrou entrada na placa,
ver [[01 - Mesa 7i92 Placa Chinesa]])

Nao ha mais botao fisico de MDI. O MDI continua na tela — digitar na caixa
MDI ja troca o modo sozinho.

### AUTO e MANUAL: comando direto, sem 'toggle'

Como sao **dois botoes**, um pra cada modo, nao precisa guardar estado
nenhum: cada toque e' o comando. O halui atende esses pinos na **borda de
subida** (medido no sim), entao botao momentaneo serve direto.

```
GPIO.024 ----------------------------------> halui.mode.auto
GPIO.025 --> and2 (nao rodando, nao pausado) -> halui.mode.manual
                                             \-> dino_painel.manual (tela)
```

O AUTO nao leva trava: pedir AUTO com um programa rodando ja' e' o modo
vigente, entao o halui nao faz nada.

### MANUAL e' ignorado com programa rodando ou pausado

Decisao do operador (2026-10-16): um esbarrao no botao nao pode derrubar o
ciclo. Para parar, PAUSA no painel ou PARAR na tela.

A trava e' na **entrada**, antes de virar comando — senao o pedido ficaria
represado e dispararia sozinho no instante em que o programa acabasse.

Com isso o **interlock antigo deixou de existir**. Ele parava o programa
quando a chave saia do AUTO; sem chave nao ha "posicao fora do AUTO" pra
detectar. O Cycle Start fisico continua so' valendo em AUTO, mas agora
olhando `halui.mode.is-auto` (o modo de verdade) em vez do nivel do botao.

### MANUAL abre o EDITAR junto

Pedido do operador: "manual ativa o modo editar sempre junto". O mesmo
sinal `btn-manual` vai pro componente `dino_painel` (criado no customs.py,
netado no `probe_basic_postgui_fix.hal`). A classe `BotoesDoPainel` le a
**borda de subida** a cada 50 ms e clica na aba EDITAR.

Detalhes que valem lembrar:
- as abas do painel direito (JOG / ZERO PECA / DRO / EDITAR) sao
  `autoExclusive`, ou seja, um grupo de radio. Clicar na que ja' esta
  aberta **nao** a fecha — por isso tocar MANUAL varias vezes e' seguro;
- so' na borda: segurar o botao nao fica reabrindo;
- **o contrario nao acontece**: apertar AUTO nao fecha o EDITAR. Fechar
  sozinho travaria o editor com alteracao na tela ainda nao salva.

### RODAR DA LINHA (2026-10-16)

Aproveita o fio que era do seletor de eixo do MPG. Aperta o **EXEC. DA
LINHA** da tela: arma o programa na linha (a do cursor no editor, ou a
salva no DEF. LINHA N) e deixa **pausado** — quem usina e' o INICIAR
depois.

Nao precisa de trava: o `_run_from_line_armed` so' atua com o
interpretador IDLE, entao um toque no meio de um corte nao faz nada.

**Nao foi ligado: nao sobrou entrada na placa.** Procuramos uma, e o que
se achou foi que o unico fio livre do painel ja' e' o do MANUAL
(GPIO.025), e que os pontos soldados dos sete I/O que o firmware deixa
livres nao chegam no FPGA. Medicao e detalhes em
[[01 - Mesa 7i92 Placa Chinesa]].

**Solucao: o botao foi pro CLP**, que tem I/O sobrando (X4 -> M204 ->
`ams32.status.04`). O lado do LinuxCNC ja' esta ligado; falta o bloco no
ladder. Ver [[08 - PLC AMS32ES2]].

### Por que CLICAR no botao da tela, e nao repetir a logica

Tanto o MANUAL quanto o RODAR DA LINHA **clicam o botao da interface** em
vez de refazer o que ele faz. O caminho passa a ser o mesmo que o dedo do
operador percorre, com as mesmas travas — e quando a logica da tela
mudar, o botao fisico acompanha sozinho.

### Refrigerante: esse sim usa 'toggle'

Um botao so' pra duas acoes, entao precisa lembrar o estado: o `toggle`
transforma o toque num nivel, e o nivel manda ligar ou desligar.

```
GPIO.023 --> and2 (maquina ligada?) --> toggle.refrig --> halui.flood.on
                                                   \-> NOT -> halui.flood.off
```

Debounce de 30 ms (`setp toggle.*.debounce 30`, servo-thread de 1 ms).
So' aceita toque com a maquina ligada: aperto com a maquina desligada nao
faria nada na bomba e so' deixaria o nivel desencontrado.

E' a MESMA bomba que o M8/M9 do programa liga — `coolant-flood` vai pro
`ams32.cmd.00` (PLC) no postgui.

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

## Preco do desenho: um toque perdido (so' no refrigerante)

O nivel do `toggle` nao le o estado real da bomba. Se ela for ligada ou
desligada por fora — o G-code com M8/M9, o botao FLUIDO da tela — o nivel
fica desencontrado e o **primeiro toque seguinte vira no-op**; o segundo
ja acerta. Nao trava nada e nao briga com ninguem.

Os botoes de modo nao tem esse problema: sao comando direto, sem estado
guardado.

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
soltas: aperta/solta de verdade, toque durante programa rodando e pausado,
maquina desligada, e cada volante contando so' no seu eixo. O MANUAL
abrindo o EDITAR foi testado no sim, vindo do DRO e do JOG. Ver
[[23 - Erros e Solucoes]].

## Status

Era chave seletora desde 2026-04-06. Virou botao de pulso unico em
2026-10-16 e, no mesmo dia, dois botoes separados (AUTO e MANUAL) quando o
painel ficou pronto. **Nao testado na maquina ainda.**
