# 16 - Interface v2: Tema Fanuc, Traducao PT-BR e Atalhos

Sessao grande de UI/UX (fechada 2026-07-05). ~30 mudancas na interface e
fluxos de operacao. Backups da versao anterior: `*.before-fanuc` e
`*.before-ptbr` no config.

## Tema Fanuc/industrial (re-tema completo)

- Grafite flat (#242729/#2E3234/#3A3F43) no lugar do escuro+cobre com degrades.
- **Semantica IEC:** CYCLE START=verde (#1B9E3E), PARAR=vermelho (#C62828),
  FEED HOLD ativo=ambar (#FFB300, texto preto), LIGAR=verde ao ligar,
  E-STOP=vermelho (rule PyDM ja existia).
- **Acento ciano** (#00838F) pra aba selecionada / MAN-AUTO-MDI / toggles.
- **DROs verde-sobre-preto** (#00E676 / #0D0F0E) estilo Fanuc - inclui
  S WORD, overrides, contador. DESG continua ambar (diferencia desgaste).
- Sliders de override: preenchimento ciano flat, trilho escuro, handle claro.
- Mecanica: QSS reescrito + script `retheme_ui.py` (587 substituicoes de
  literais nos 4 .ui). CYCLE START **pulsa** (verde claro/escuro 600ms,
  texto preto) enquanto roda - `_wire_cycle_start_pulse` no customs.py.

## Traducao PT-BR

- 148 strings de botoes/abas/menus (script `translate_ui.py`, so texto
  visivel - actionNames/MDICommand/rules intactos).
- Termos CNC mantidos: JOG, MDI, DRO, FEED, SPINDLE, HOME, G-codes.
- **ZERO PECA** = offsets G54-G59.3 (CORRETOR ficou so pra ferramenta,
  como no touch off - nomenclatura correta BR).

## Aba EDIT (painel direito, junto de JOG/OFFSET/DRO)

- Editor de G-code agora e **read-only por padrao**; so edita com a aba
  EDIT selecionada (gate via `EditorReadOnly`).
- Aba EDIT tem FIND/REPL, SAVE, COPIAR, COLAR (sairam da barra do editor).
- **Atalhos de teclado bloqueados durante edicao** (ShortcutOverride filter)
  - digitar G-code nao move eixo nem liga nada.
- Maiusculas automaticas ao digitar/substituir no editor.
- Nao usar `user_sb_tab` (o backend do ProbeBasic esconde ele); aba nova
  `edit_tab` page=4 + `sb_page_5`.

## RUN FROM LINE seguro + SET LINE N

- RUN FROM LINE **arma pausado** na linha (cursor ou linha salva) e so roda
  no CYCLE START. Aviso na tela some sozinho ao dar resume.
- **SET LINE N**: memoriza linha de partida POR PROGRAMA (QSettings), pra
  nao procurar toda vez. Botao vira "LINE N 12" quando ativo.
- Botao no painel inferior (no lugar do MIST), logo abaixo do CYCLE START.
- SET QUE + campo numerico do ProbeBasic: escondidos (codigo os referencia
  no boot - NAO deletar). FIND M6 maior (200x42) e continua funcional.

## Atalho de desgaste (DESG X / DESG Z)

- Coluna do T: botoes DESG X / DESG Z **clicaveis** - dialogo NAO-modal
  (modal bloquearia o teclado virtual!) soma ajuste ao desgaste da
  ferramenta ativa. X em DIAMETRO. Spinbox com locale C (aceita '.').
- `interpretText()` antes de ler (botoes NoFocus nao geram focus-out).
- Enter do teclado virtual = APLICAR direto.
- Novos metodos: `adjustWearAxisForTool` / `adjustWearAxisCurrentTool`
  (wear_tool_table.py).
- C? (angulo da placa) e marcha (M01 - 2360 RPM) moveram do DRO pra essa
  coluna. G7/G8 e IR P/ G30/HOME ocultos ali.

## Tool table / DRO

- **Auto-save no Enter** (qualquer coluna) + **soma incremental** no
  X DESG/Z DESG (Fanuc-style: digitou 0.05 com 0.15 -> 0.20).
- X DESG fala DIAMETRO na UI (wear interno em raio; fator via G7/G8 vivo).
- Edicao com **1 clique** (editTriggers CurrentChanged/SelectedClicked).
- DRO custom: **modo alternavel** (botao AMPLIAR/TABELA no rodape) - tabela
  detalhada OU X/Z gigantes (64pt) pra ler de longe. Persiste (QSettings).

## Bugs corrigidos

- **X do G54 dividia por 2 a cada SAVE** (era o "bug Z->X"): G10 L2 em G7
  interpreta X como diametro. Fix: save do offset envolve em M70/G8/.../M72
  (mesmo padrao do touch_off_x.ngc). wear_offset_table.py.
- **M101 (contador de pecas)**: script nao existia; agora versionado em
  `mcodes/M101` + `USER_M_PATH = mcodes` no ini (a copia em nc_files sumia).
- MPG: x4-mode desligado (1 count/clique) + incrementos 0.005/0.01/0.05/0.1.
- Angulo da placa: comp `chuck_angle.py` (revs % 1 * 360, seguro em M4).
- Backplot: PAN sempre ativo + PGM EXT automatico ao carregar programa.
- Logo EVO no backplot: implementada mas **desativada**
  (`_LOGO_BACKPLOT_ATIVA = False` no customs.py) - melhorar a arte antes.

## Pendencias de teste na maquina

- Fix do save do offset (SAVE 2x sem editar -> X nao pode mudar).
- Pulso do CYCLE START; teclado virtual no dialogo DESG; modo AMPLIAR.
- M101 contando (reiniciar LinuxCNC pra ler USER_M_PATH).
