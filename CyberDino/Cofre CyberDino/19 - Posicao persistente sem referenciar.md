# 19 - Posicao persistente (ligar sem referenciar)

**Status: IMPLEMENTADO em 2026-10-04**, testado no sim, PENDENTE na maquina.

Decisao do operador (2026-10-04): os eixos nao se mexem com a maquina
desligada, entao a posicao salva vale. Sem dialogo de confirmacao — se
precisar referenciar de novo, ele ve pelo olho e roda o script. O
`restaurar` tem que deixar "como se nunca tivesse sido desligado".

Objetivo: ligar o LinuxCNC e ja ter as coordenadas certas, sem passar a
chave de referencia toda vez. A posicao e' salva enquanto a maquina
trabalha e restaurada no boot seguinte.

## O que a maquina oferece hoje (conferido no config)

| | |
|---|---|
| Acionamento X/Z | stepgen do 7i92 (step/dir) para servos AMS32 |
| Realimentacao de posicao | **nenhuma** — `x-pos-fb` vem do proprio `stepgen.00.position-fb`, ou seja, e' o comando, nao a posicao real |
| Chave de referencia | **uma so**, compartilhada (GPIO.014, NF em serie), `HOME_IS_SHARED=1` |
| Sequencia | X (1) depois Z (2), sem indice (`HOME_USE_INDEX=NO`) |
| Limites de curso | so' por software (MIN_LIMIT/MAX_LIMIT) |
| Politica | `NO_FORCE_HOMING = 0` — exige referenciar antes de rodar |

Os dois fatos que mandam no projeto: **o LinuxCNC nao sabe onde o eixo
esta de verdade** (malha aberta) e **nao ha batente fisico protegendo** —
se a posicao restaurada estiver errada, os limites de software tambem
estao, e a maquina vai contra o fim de curso mecanico.

## O mecanismo (documentado, nao inventado)

LinuxCNC 2.9.10, secao 4.5.6.14 *Immediate Homing*:

```
HOME_SEARCH_VEL = 0
HOME_LATCH_VEL  = 0
HOME_USE_INDEX  = NO
HOME_OFFSET     = <posicao salva>
HOME_SEQUENCE   = 1 (ou outro valido)
```

> HOME_SEARCH_VEL = 0 — "A value of zero means assume that the current
> location is the home position for the machine."

Ou seja: com esses valores o REFERENCIAR **nao move nada** — ele assume
que o eixo ja esta no home e atribui `HOME_OFFSET` aquela posicao. Entao
basta gravar a ultima posicao conhecida e escreve-la em HOME_OFFSET antes
do LinuxCNC subir.

`HOME` (destino depois de referenciar) tem que ficar **igual** a
HOME_OFFSET, senao a maquina sai andando ate o HOME assim que referenciar.

O INI aceita `#INCLUDE arquivo` (secao 4.4.1.5), entao a posicao salva
entra por um fragmento gerado, sem reescrever o INI principal.

## Como ficou (implementado)

| Peca | O que faz |
|---|---|
| `salva_posicao.py` | componente HAL; grava a posicao nos `.inc` a cada parada do eixo, a cada 500 ms enquanto anda, e no SIGTERM |
| `home_joint0.inc` / `home_joint1.inc` | bloco de referenciamento ATIVO, lido pelo INI com `#INCLUDE` |
| `home_chave_joint*.inc` | os valores originais (busca na chave), usados como molde |
| `referenciar_na_chave.sh` | devolve o referenciamento na chave pro proximo boot (terminal) |
| Botao **REFERENCIAR NA CHAVE** (aba CUSTOMS) | o mesmo, pela tela, com o modo atual escrito em cima e opcao de reiniciar o LinuxCNC na hora |
| `_wire_posicao_salva` (customs.py) | referencia sozinho ao LIGAR, quando o `.inc` ativo e' do tipo posicao salva, e avisa na tela de onde veio |

O sim grava com prefixo `sim_` — jogar no sim nao mexe no ponto de partida
do torno de verdade.

**Quem escreve nos .inc e' SO o salva_posicao.py.** O botao e o script
apenas criam a bandeira `armar_chave.flag`; o componente ve a bandeira,
escreve os moldes da chave e para de salvar ate o proximo boot. Se o botao
escrevesse direto, o encerramento regravaria a posicao por cima e
desarmaria sozinho — foi a primeira versao, e quebrava.

O modo de referenciamento vem do INI, que so' e' lido no boot: nao da pra
trocar com o LinuxCNC no ar. O modulo de homing padrao nao expoe isso em
pino HAL, e o `homecomp` e' so' um molde pra compilar um modulo em C.

### Teste no sim (2026-10-04)

| Fase | Resultado |
|---|---|
| Ligar com posicao salva X=111.111 Z=-222.222 | referenciou sem mover, DRO exatamente nesses valores |
| Mover e encerrar | `.inc` e json atualizados (`motivo: encerramento`) |
| Religar | subiu em X=111.121 Z=-222.232, onde a sessao parou |
| So apertar LIGAR, sem tocar em REFERENCIAR | referenciou sozinho em X=77.777 Z=-88.888 |
| `referenciar_na_chave.sh` | `.inc` volta a ter `HOME_SEARCH_VEL = -20` |
| Botao da aba CUSTOMS | armou a chave, e **mover depois nao desfez** (o componente parou de salvar) |
| Rotulo do botao | passou de "posicao salva (11:00:00)" para "busca na CHAVE no proximo boot" sozinho |

O referenciamento NA CHAVE nao da pra testar no sim: sem o 7i92 a
GPIO.014 nunca fecha e o home nunca completa.

### Estado atual dos arquivos

Os `home_joint*.inc` da maquina real estao com **busca na chave** — o
primeiro boot depois dessa mudanca referencia normal, e dai em diante a
posicao passa a ser salva sozinha.

## Rotina: referenciar no fim de curso quando quiser

O modo de referenciamento vem do INI, que so' e' lido no BOOT — nao da pra
trocar com o LinuxCNC no ar. O modulo de homing padrao nao expoe isso em
pino HAL e o `homecomp` e' so' um molde pra compilar um modulo em C. Entao
a rotina tem tres passos, e o reinicio e' inevitavel:

**1. Armar.** Aba CUSTOMS -> **REFERENCIAR NA CHAVE**. Ele pergunta se quer
reiniciar o LinuxCNC na hora (Sim reinicia sozinho; Nao so' arma, e vale no
proximo boot). Pelo terminal, com o LinuxCNC fechado:
`./referenciar_na_chave.sh`.

**2. Reiniciar.** Na volta a maquina sobe SEM referencia e com um aviso na
tela: "Referenciamento NA CHAVE armado. Ligue a maquina e aperte REF ALL".

**3. Referenciar.** LIGAR e REF ALL — X busca a chave a -20 mm/s, latch a
2, termina em HOME=5.0; depois o Z, igual sempre foi.

Terminado isso o `salva_posicao.py` volta a gravar sozinho: a proxima vez
que ligar ja sobe com a posicao salva. Nao precisa desfazer nada.

### Armadilha paga (2026-10-04): o repasse por bandeira

O botao criava uma BANDEIRA e o salva_posicao.py a atendia. Dependia de
tempo e quebrou duas vezes na maquina: o encerramento gravava a POSICAO por
cima dos moldes da chave e o pedido sumia calado — o REF ALL referenciava
parado como se nada tivesse sido pedido. Botar o botao pra esperar o
atendimento ajudou, mas a segunda tentativa falhou do mesmo jeito.

O rastro estava sempre no proprio arquivo: a hora gravada no `.inc` era a
do ENCERRAMENTO, nao a do clique. E o `Dino_Evo.ini.expanded` (o INI que o
LinuxCNC gera resolvendo os `#INCLUDE`, no boot) confirmava com que valores
cada sessao tinha subido.

**Desenho atual, sem repasse:** quem foi clicado escreve. O botao e o
script gravam os moldes da chave e marcam `modo_referenciamento.txt` =
`chave`. O componente OBEDECE esse arquivo e o rele ANTES DE CADA
GRAVACAO, inclusive na de saida — entao nao existe instante em que um
pedido possa ser perdido ou sobrescrito.

Quando o referenciamento fisico conclui, o proprio componente devolve o
estado para `posicao` e volta a salvar.

### Como CONFERIR se a posicao salva estava certa

So olhar o DRO nao prova nada — ele mostra o que foi restaurado, certo ou
errado. O teste de verdade:

1. com a posicao restaurada, encoste a ferramenta num ponto que de pra
   reconhecer (face da placa, um ressalto) e anote o DRO;
2. rode a rotina acima e referencie na chave;
3. mande voltar: `G53 G0 X<anotado> Z<anotado>`;
4. se a ferramenta parar no MESMO ponto fisico, a posicao salva valia.

## O que ficou de fora (do plano original)

Por decisao do operador, estas pecas do plano NAO foram feitas:

- **dialogo de confirmacao no boot** — ele confere pelo olho;
- **invalidacao automatica** (saida suja, alarme de servo, ferror, E-stop);
- **CONFERIR POSICAO** tocando a chave.

Se um dia a posicao salva trair, sao essas tres que entram.

## Riscos (aceitos conscientemente)

- **Malha aberta.** O LinuxCNC registra o que mandou, nao o que o eixo
  fez. Volante manual, empurrao, drive destravado, perda de passo ou
  colisao com o LinuxCNC fora do ar = posicao salva errada, e os limites
  de software deslocados junto.
- **Falta de energia.** O salvamento a cada 500 ms pode estar meio segundo
  atrasado. Parado nao faz diferenca; em rapido, sao alguns milimetros.
- **Alarme de servo.** O AMS32 avisa, mas o LinuxCNC nao sabe quanto o
  eixo escorregou.

O operador decidiu conviver com isso: os eixos nao se mexem desligados, e
se desconfiar ele olha a maquina e roda o `referenciar_na_chave.sh`. O
botao REFERENCIAR continua na tela do mesmo jeito.

## O que NAO funciona (ja descartado)

- `NO_FORCE_HOMING = 1` sozinho: libera rodar sem referenciar, mas a
  posicao de maquina comeca em zero onde quer que o eixo esteja — os
  limites de software passam a proteger o lugar errado.
- `G92` / zero-peca para "colocar" a posicao: mexe no offset de peca, nao
  na posicao de maquina. Os limites continuam errados.
- Mudar HOME_OFFSET com a maquina ligada: o INI e' lido no boot; nao ha
  pino HAL para isso no modulo de homing padrao.
