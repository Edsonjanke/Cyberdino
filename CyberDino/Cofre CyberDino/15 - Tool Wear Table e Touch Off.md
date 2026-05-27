# Tool Wear Table e Touch Off

Tabela de ferramentas com split geometria/desgaste estilo Fanuc + auto-zero do
desgaste ao realizar touch off.

## Arquivos

| Arquivo | Funcao |
|---------|--------|
| `dino_widgets/wear_tool_table.py` | WearToolTable - tool table com colunas XW/ZW |
| `dino_widgets/wear_offset_table.py` | WearOffsetTable - offset table (G54..G59) com XW/ZW |
| `tool_wear.json` | Sidecar: desgaste puro por numero de ferramenta `{"1": {"x": ..., "z": ...}}` |
| `offset_wear.json` | Sidecar: desgaste puro por work offset `{"G54": {"x": ..., "z": ...}}` |
| `subroutines/touch_off_x.ngc` | Touch off em X (calcula novo offset de ferramenta) |
| `subroutines/touch_off_z.ngc` | Touch off em Z |
| `user_tabs/customs/customs.py` | Wiring postgui dos signals touch_off -> clearWear |

## Como funciona o split geom/wear

- `tool.tbl` continua guardando o **total** (geometria + desgaste). LinuxCNC nao sabe da existencia do split.
- O sidecar (`tool_wear.json`) guarda apenas a parcela **desgaste**.
- Na UI, a coluna X (geom) e calculada como `total - wear`. As colunas amarelas XW/ZW exibem `wear`.
- Ao editar:
  - X (geom) -> `tool.tbl X = novo_geom + wear_atual`
  - XW (desgaste) -> `tool.tbl X = total_atual - old_wear + new_wear` (geom invariante)

## Auto-zero do desgaste no touch off (2026-05-27)

**Problema:** Touch off escrevia o offset total via `G10 L1` mas o sidecar continuava
com o desgaste antigo. Resultado: a coluna X exibida ficava deslocada do que o
operador acabou de tocar (display = total_novo - wear_antigo).

**Solucao:** Apos clicar TOUCH X, o desgaste **X** da ferramenta atual e zerado
automaticamente no sidecar. Touch Z zera apenas **Z**. Mantem o desgaste do
outro eixo intacto (comportamento Fanuc).

**Mecanica:**
1. Slot `WearToolTable.clearWearAxisCurrentTool(axis)` adicionado em
   `dino_widgets/wear_tool_table.py`. Le `STATUS.tool_in_spindle.value`
   pra saber qual ferramenta.
2. Wiring postgui em `user_tabs/customs/customs.py` -> funcao
   `_wire_touch_off_wear_clear()` que conecta os signals
   `touch_off_x.clicked` e `touch_off_z.clicked` ao slot do widget
   (com argumento 'x' ou 'z' respectivamente).
3. O NGC roda assincrono via mdi(); o clearWear roda imediatamente no slot.
   Quando o `G10 L1` do NGC chega no LinuxCNC, o plugin recarrega `_tool_table`
   sobrescrevendo qualquer ajuste local. Como o wear ja foi gravado em
   `tool_wear.json` com 0, o display final fica `total_novo - 0 = total_novo`. OK.

## Bug em investigacao (2026-05-27)

**Sintoma:** Na `WearOffsetTable` (linha G54), editar coluna Z (geometria) imediatamente
muda o valor exibido na coluna X. Magnitude do delta nao identificada.

**Estado atual:** Logging adicionado em `WearOffsetModel.setData` (linha ~161 de
`dino_widgets/wear_offset_table.py`). Reproduzir o bug e analisar
`~/linuxcnc_debug.txt` (ou stderr do qtvcp) para identificar:

- Se `index.row()` recebido em setData ja vem mapeado pela proxy;
- Se `_offset_table` tem rows compartilhando a mesma lista (shallow copy do
  `DEFAULT_OFFSET` no plugin qtpyvcp);
- Se o signal `offset_table_changed` do plugin re-dispara updateModel com dados
  stale logo apos a edicao.

Apos identificar, remover os `LOG.info` e aplicar o fix.

## Verificacao end-to-end

**Touch off auto-zero:**
1. Carregar T1 (`M6 T1`). Editar XW=0.3 e ZW=0.2 da T1. Confirmar
   `tool_wear.json` tem `{"1": {"x": 0.3, "z": 0.2}}`.
2. Touch X numa peca conhecida. Esperado: tool_wear.json passa a ter
   `{"1": {"x": 0.0, "z": 0.2}}` (ou T1 removido se ambos zerarem).
3. Coluna X (geom) reflete o offset que o NGC acabou de calcular,
   sem deslocamento residual.
4. Repetir para Z -> apenas ZW vai a zero.

**Bug Z->X:**
1. Abrir WearOffsetTable, linha G54. Anotar X atual exibido.
2. Editar Z para novo valor, Enter. Conferir se X exibido permanece igual.
3. Coletar log e identificar causa-raiz.
