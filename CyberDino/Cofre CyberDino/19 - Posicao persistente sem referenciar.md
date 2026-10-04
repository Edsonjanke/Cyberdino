# 19 - Plano: posicao persistente (ligar sem referenciar)

**Status: PLANO, nada implementado.** Escrito em 2026-10-04.

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

## Pecas a construir

**1. `salva_posicao.py`** — componente HAL userspace (como o
`partcounter.py` e o `chuck_angle.py` que ja existem).
- Le os sinais que ja existem no HAL: `x-pos-fb`, `z-pos-fb` (posicao de
  maquina, sem offset de peca) e `joint.N.homed`.
- Grava `posicao_salva.json` por escrita atomica (tmp + rename, pra nao
  deixar arquivo pela metade se faltar energia no meio).
- Cadencia: a cada 500 ms, so' quando mudou mais que 1 um.
- So' salva com a maquina REFERENCIADA — posicao de maquina nao
  referenciada nao vale nada.
- No SIGTERM grava uma ultima vez e marca `saida_limpa: true`.

**2. `restaura_posicao.py`** — roda ANTES do LinuxCNC, pelo atalho de
inicializacao.
- Le o json e gera `home_joint0.inc` / `home_joint1.inc` com HOME,
  HOME_OFFSET e as velocidades zeradas.
- Se o json nao existir, estiver sujo ou velho, gera os fragmentos com o
  homing NA CHAVE (os valores de hoje) — o padrao e' o seguro.

**3. INI** — em cada `[JOINT_n]`, trocar as cinco linhas de homing por
`#INCLUDE home_jointN.inc`.

**4. Dialogo de confirmacao no boot** (customs.py) — mostra a posicao
restaurada, quando foi salva e por que ela e' (ou nao) confiavel, com dois
botoes: **CONFIRMAR POSICAO** e **REFERENCIAR NA CHAVE**. Enquanto nao
responder, `motion.homing-inhibit` segura o referenciamento.
Nao-modal, por causa do teclado virtual (licao da v2).

**5. Invalidacao automatica** — a posicao salva vira suspeita quando:
- a saida nao foi limpa (sem SIGTERM: queda de energia, kill, travamento);
- houve alarme de servo AMS32 desde o ultimo salvamento;
- houve erro de seguimento (ferror);
- o arquivo tem mais de N dias;
- a maquina ficou em E-STOP (com o drive solto, o eixo pode ter sido
  movido na mao).
Em qualquer um desses casos o dialogo ja abre sugerindo referenciar.

**6. (Opcional) CONFERIR POSICAO** — rotina que toca a chave
compartilhada e compara com o esperado. Se divergir mais que a
tolerancia, avisa. E' a unica forma de a maquina *descobrir sozinha* que
a posicao salva envelheceu.

## Ordem de execucao

| Fase | O que | Como se prova |
|---|---|---|
| 0 | Provar o Immediate Homing no sim | REFERENCIAR com HOME_OFFSET=123.456 tem que deixar o DRO em 123.456 **sem mover** |
| 1 | So o `salva_posicao.py`, sem restaurar nada | rodar alguns dias e conferir se o json bate com o DRO ao desligar |
| 2 | Restauracao + dialogo de confirmacao | desligar numa posicao conhecida, religar e conferir o DRO antes de liberar a maquina |
| 3 | Invalidacao automatica + CONFERIR POSICAO | simular queda de energia (kill -9) e ver se o dialogo exige referenciar |

A fase 1 e' a que da confianca: ela mede o erro **sem** ninguem depender
do resultado. So' depois de ver o valor bater e' que a fase 2 entra.

## Riscos (o motivo de o dialogo nao ser opcional)

- **Malha aberta.** O LinuxCNC registra o que mandou, nao o que o eixo
  fez. Volante manual, empurrao, drive destravado, perda de passo ou
  colisao com o LinuxCNC fora do ar = posicao salva errada, e os limites
  de software deslocados junto.
- **Falta de energia.** O salvamento a cada 500 ms pode estar meio segundo
  atrasado. Parado nao faz diferenca; em rapido, sao alguns milimetros.
- **Alarme de servo.** O AMS32 avisa, mas o LinuxCNC nao sabe quanto o
  eixo escorregou.

Por isso: referenciar na chave continua a um toque, e nenhuma dessas
fases remove o REFERENCIAR da tela.

## O que NAO funciona (ja descartado)

- `NO_FORCE_HOMING = 1` sozinho: libera rodar sem referenciar, mas a
  posicao de maquina comeca em zero onde quer que o eixo esteja — os
  limites de software passam a proteger o lugar errado.
- `G92` / zero-peca para "colocar" a posicao: mexe no offset de peca, nao
  na posicao de maquina. Os limites continuam errados.
- Mudar HOME_OFFSET com a maquina ligada: o INI e' lido no boot; nao ha
  pino HAL para isso no modulo de homing padrao.
