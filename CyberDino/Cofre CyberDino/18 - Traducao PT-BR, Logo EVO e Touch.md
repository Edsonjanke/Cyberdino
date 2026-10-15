# 18 - Traducao PT-BR Completa, Logo EVO e Ergonomia Touch

Sessao de 2026-08-02, depois da [[16 - Interface v2 Fanuc e Atalhos]].

## Traducao completa

A v2 traduziu 148 strings; esta fechou o resto — inclusive o **painel de
botoes do operador** (`user_buttons/template_user_buttons/`): EXEC. DA LINHA,
DEF. LINHA N, BLOCO A BLOCO, PARADA M01, PAUSA, FLUIDO, LIMPAR PGM.

APALPADOR **nao** foi traduzido: a aba continua oculta.

**Armadilha:** botao que tem `rules` do qtpyvcp ignora o texto do `.ui` — a
regra reescreve o texto em tempo de execucao. Foi o caso do CYCLE START, que
continuava em ingles mesmo com INICIAR no arquivo. Traduzir dentro da regra.

Strings com espacos de alinhamento (menu ARQUIVO) precisam manter os espacos,
senao o botao desalinha.

## Logo EVO

Logos oficiais baixadas do repo Evo-SI-ERP para `logo/` (13 arquivos).

Usar sempre a versao **mono branca** na interface: a colorida tem 62% da arte
com contraste 1,22 no fundo escuro — some.

Onde esta:
- **Backplot** — marca d'agua, logo completa, opacidade 0.50, canto inferior
  direito. Ligada por `_LOGO_BACKPLOT_ATIVA = True` no customs.py (na v2 ela
  existia mas estava desligada).
- **Aba GERAR PGM** — rodape da coluna de operacoes.

**Armadilha do VTK:** a logo horizontal e' 3,24:1 e o `vtkLogoRepresentation`
por padrao estica pra dentro do retangulo do `SetPosition2` — sai achatada.
Precisa `ProportionalResizeOn()`, mais `SetRenderer()` + `BuildRepresentation()`
pra aparecer.

Foi testada tambem na barra do MDI e **removida** (2026-08-02): poluia.

## Contraste e alvo de toque

- Verde do CYCLE START #1B9E3E -> **#157A30** e borda #3A3F43 -> **#5A6268**
  (o texto branco no verde antigo nao passava no contraste minimo).
- Botoes do menu ARQUIVO: 35px -> **48px** de altura (alvo de toque
  industrial). Sobraram ~90 botoes menores que 48px na tela principal —
  nao mexidos porque nao da pra conferir o layout fora do LinuxCNC.
- Combo de roscas: 20pt, linhas da lista de **52px**. Sao 97 roscas
  escolhidas com o dedo; a altura padrao (~25px) fazia errar o item.

## Gerenciador de arquivos (aba ARQUIVO)

Tres defeitos so' visuais, medidos rodando o sim sob Xvfb:

- **PASTA ACIMA** tinha largura travada em 110px (min = max) e o texto com o
  icone pede 125px — a frase passava por cima da borda. Foi para 140px.
- **MOSTRAR USB** era o unico botao que ainda tinha o estilo antigo do
  ProbeBasic (gradiente escuro, borda preta, 16pt, 35px de altura) — destoava
  de toda a fileira. Agora segue o tema, com 48px como os vizinhos. O
  `:checked` foi fixado na cor normal: quem avisa o estado e' o texto
  (MOSTRAR/OCULTAR), nao a cor.
- Com o painel do USB aberto sobra so' 592px para SEIS botoes, e a soma a
  14pt dava 576+espacos: NOVO ARQUIVO ficava cortado. A fileira foi para
  13pt (soma 555) e as larguras minimas para 80px.

Os botoes **funcionam** — foram testados com clique de mouse real e
verificando que nada os cobre. O que estava errado era so o desenho.

## Atalhos de teclado das abas

**Ctrl+1 a Ctrl+9** trocam de aba, na ordem em que aparecem. Feito em
`_wire_atalhos_abas` (customs.py), agendado DEPOIS do `_hide_probe_tab` —
o APALPADOR sai com removeTab, entao a numeracao segue as abas visiveis.

O "CTRL+N" **nao entra no texto da aba**: vai como um QLabel proprio preso
ao lado direito (`setTabButton(i, QTabBar.RightSide, ...)`), em azul claro
#B3E5FC e 11pt. E' o unico jeito de dar cor e tamanho so' a essa parte,
porque o texto de uma aba e' uma string sem formatacao por pedaco.

Dois detalhes que custam caro se esquecer:
- o rotulo leva `WA_TransparentForMouseEvents`, senao um toque em cima do
  "CTRL+N" cai no QLabel e a aba nao troca;
- o titulo da aba continua o nome puro, o que mantem a preferencia de "aba
  inicial" dos AJUSTES funcionando (o probe_basic casa pelo TEXTO da aba
  durante o boot).

Na aba selecionada o azul cai para 3.3:1 sobre o ciano — legivel, e e'
justamente a aba onde o atalho nao importa. Nas outras fica 8.8:1.

**A barra esta no limite:** as 9 abas com a etiqueta somam 1406px dos
1410px disponiveis a 1920x1080. Uma aba a mais, ou um nome mais longo, e a
barra ganha setas de rolagem.

**No modo EDIT todos os atalhos valem** (decisao do operador,
2026-10-15). O `_EditShortcutBlocker` continua no codigo, mas desligado
pela chave `_BLOQUEAR_ATALHOS_NO_EDIT = False` no topo do customs.py.
Se um dia voltar a True, continuam passando Ctrl+1..9, Ctrl+S e F6 — os
tres so' mexem na tela ou gravam o arquivo que esta aberto.

**O risco esta medido e e' real:** `R` e' *Executar Programa*, e R aparece
em G-code o tempo todo — raio de arco (`G2 X.. Z.. R5`), plano do ciclo
(`G81 R2`), degressao do G76. Digitar um raio com a aba EDITAR aberta
DISPARA o programa. `O` (letra das sub-rotinas) abre o dialogo de arquivo,
`Ctrl+R` recarrega descartando o que foi digitado e `Ctrl+Q` fecha o
LinuxCNC. Para voltar a bloquear, basta a chave em True.

### Todos os atalhos do LinuxCNC nesta maquina

| tecla | acao | de onde |
|---|---|---|
| **R** | **Executar Programa** | menu / .ui |
| O | Abrir arquivo | menu / .ui |
| Ctrl+O | Abrir arquivo | menubar.yml |
| Ctrl+R | Recarregar programa | menu / .ui |
| Ctrl+Q | Sair do LinuxCNC | menubar.yml |
| F1 | Alternar E-STOP | menu / .ui |
| F2 | Ligar/desligar maquina | menu / .ui |
| F7 | Neblina | menu / .ui |
| F8 | Refrigerante | menu / .ui |
| Ctrl+1..9 | trocar de aba | customs.py |
| Ctrl+S | salvar | customs.py |
| **F6** | **procurar a proxima M6** | customs.py |

Ctrl+C/V/X/Z/A **nunca** foram bloqueados: o editor trata essas teclas por
conta propria, sem atalho registrado, entao o filtro nem as via.

## Editor de G-code: Ctrl+S e o zoom do backplot

**Ctrl+S salva** (QKeySequence.Save, ligado no `_wire_edit_mode`). So' vale
com o editor destravado — fora do modo EDIT a tecla nao faz nada, pra nao
gravar um arquivo que o operador nem abriu pra editar. Esta na lista de
excecoes do `_EditShortcutBlocker`, junto com Ctrl+1..9.

**O backplot nao reenquadra mais a cada salvada.** O slot nativo
`setProgramViewWhenLoadingProgram(True)` reenquadra em TODA carga, e salvar
no editor recarrega o mesmo arquivo: dava zoom num trecho, salvava, e a
vista pulava pro programa inteiro. Agora o flag nativo fica DESLIGADO e o
enquadramento e' chamado por nos no `STATUS.file.notify`, so' quando o
caminho do arquivo muda. Programa novo enquadra; mesmo arquivo recarregado
mantem o zoom.

Detalhe: `setViewProgram` desiste calado enquanto `program_bounds_actors`
estiver vazio, entao a chamada e' repetida ate a geometria existir (12
tentativas de 500ms). No sim sob Xvfb os atores nunca aparecem — o VTK nao
monta o percurso ali —, entao esse pedaco so' da pra conferir na maquina.

## Procurar no G-code (fileira do editor)

Ao lado do **PROCURAR M6** entraram **PROCURAR M30** e um **campo livre**
com botao PROCURAR (2026-10-15). ENTER no campo tambem procura — no
teclado virtual e' assim que se fecha o campo.

A busca e' por **trecho, sem diferenciar maiusculas**: `g76` acha G76 e
`T03` acha a linha da troca. E' a mesma regra que o PROCURAR M6 do
ProbeBasic ja usava, entao nao e' novidade pro operador.

Toques repetidos no mesmo termo andam pelas ocorrencias e voltam pra
primeira no fim (o contador fica por termo, num dicionario; trocar o termo
nao perde a posicao do anterior).

**O achado alimenta o EXEC. DA LINHA:** o numero da linha e' escrito no
`run_from_line_Num`, que esta oculto na tela mas continua sendo de onde o
botao de executar a partir da linha tira o ponto de partida. Era assim que
o M6 funcionava; os novos seguem o mesmo caminho.

**F6 = PROCURAR M6** (2026-10-15). O F6 estava livre: o LinuxCNC usa F1
(E-STOP), F2 (ligar), F7 (neblina) e F8 (refrigerante), e nao o F6.

O atalho **clica o botao** em vez de refazer a busca por fora. Isso importa:
o ProbeBasic guarda em que M6 parou (`current_m6_index`), entao clicando o
botao o F6 e o dedo andam pela MESMA lista. Se o F6 chamasse a busca nova,
seriam dois contadores — apertar F6 depois de tocar o botao voltaria pra
primeira M6. Conferido no sim: botao -> linha 6, F6 em seguida -> linha 9.

Codigo: `_wire_procurar_gcode` no customs.py. A rolagem e' do proprio
ProbeBasic (`janela.scroll_to_line_in_gcode`).

O "F6" **nao esta escrito no botao**: a fileira tem 491px e os quatro
widgets ja a enchem (o PROCURAR M6 tem 120px pra uma dica de 98). Por
enquanto o atalho so' aparece no tooltip.

O **PROCURAR M6 encolheu de 200px para 120..145px** pra abrir espaco — a
fileira a 1920x1080 nao tem folga sobrando.

## Armadilha: o pyuic aceita, o LinuxCNC quebra pela metade

Para dividir um QHBoxLayout em partes iguais NAO use a propriedade `stretch`
do layout. O `pyuic` compila sem reclamar (so ignora), mas o `uic.loadUi`,
que e' o que o LinuxCNC usa, estoura:

    TypeError: setStretch(self, index: int, stretch: int):
               argument 1 has unexpected type 'str'

E o pior: o widget que estava sendo montado fica pela METADE — no caso do
DRO, o `widget_big_dro` existia vazio e todos os filhos sumiam, sem erro
visivel na tela. Use `horstretch` no sizePolicy de cada widget.

Por isso existe **`tools/valida_ui.py`**: carrega o .ui com o mesmo
carregador do LinuxCNC (widgets do qtpyvcp trocados por equivalentes
simples) e acusa o erro em 2 segundos, sem subir o sim:

```bash
QT_QPA_PLATFORM=offscreen python3 tools/valida_ui.py <arquivo.ui> [prefixo]
```

## Armadilha que se repete: QSS vence setFont()

A folha de estilo da aplicacao **sobrepoe** `setFont()` e tambem o
`ForegroundRole` do item. Sintomas ja vistos: fonte calculada ficava sempre
no tamanho do tema, e as cores das roscas simplesmente nao apareciam.

Saidas:
- fonte: escrever `font-size` na folha de estilo **do proprio widget**;
- cor de item: desenhar o texto num `QStyledItemDelegate` (folha de estilo
  nao alcanca o que e' pintado a mao). A **caixa fechada** do combo nao passa
  pelo delegate — precisa de `paintEvent` proprio.

Teste de UI **tem que carregar o QSS** (`app.setStyleSheet(...)`), senao
esconde exatamente esse tipo de problema.

## Rede

Ver [[23 - Erros e Solucoes#IPv4 morto parece bloqueio do GitHub]].
