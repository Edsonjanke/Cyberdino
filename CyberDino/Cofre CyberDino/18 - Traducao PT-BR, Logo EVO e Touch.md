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
