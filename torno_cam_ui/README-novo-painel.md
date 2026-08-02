# Como adicionar uma operação nova na aba GERAR PGM

Procedimento usado no FACEAMENTO e na FURAÇÃO. Seguindo isso, um painel novo
sai em minutos e já cai alinhado — sem ajustar coordenada no olho.

Prontos: FACEAMENTO, DESBASTE EXT, DESBASTE INT (básico + avançado), FURAÇÃO.
Faltam: **CHANFRO/RAIO** e **CANAL/CORTE**.

Operação com mais de um modo (caso do desbaste interno): cada modo tem o seu
desenho e o seu conjunto de campos. Use `ImageOverlayPanel.reconfigurar()` para
trocar imagem + campos — os widgets são os mesmos, então o que foi digitado
sobrevive à troca. Rode o detector uma vez por modo (`id_basic`, `id_ext`);
campos que o detector não achar num modo provavelmente **não existem naquele
desenho** (confira o bloco `{isExt && (` no `*Panel.tsx` antes de ajustar semente).

---

## Passo a passo

### 1. Copiar a imagem de fundo
```bash
cp Evo-CNC-Guia/apps/desktop/public/<op>-bg.png torno_cam_ui/images/
```
Imagens disponíveis: `chamfer-od-bg.png`, `chamfer-id-bg.png`, `groove-bg.png`,
`corte.png`, `id-turn-bg.png`, `id-turn-ext-bg.png`.

### 2. Pegar as sementes no painel React
Abrir `Evo-CNC-Guia/apps/desktop/src/components/operations/<Op>/<Op>Panel.tsx`:
- a tabela `POS` / `POSITIONS` → `top`/`left` em **% do container**;
- as constantes `IMG_W`/`IMG_H` → o **aspect ratio do container** (atenção:
  nem sempre é o da imagem — no faceamento não é).

Copiar isso para o dicionário `SEEDS` em `torno_cam_ui/tools/detecta_caixas.py`.

### 3. Medir os retângulos
```bash
python3 torno_cam_ui/tools/detecta_caixas.py <op>
```
Sai a tabela `FIELDS` pronta. **Ajustar o `max_chars`** de cada campo para o
maior valor que ele recebe — é o que define o tamanho da fonte:

| max_chars | campo típico |
|---|---|
| 2 | número de ferramenta |
| 4 | RPM, pausa |
| 5 | profundidade, folga, diâmetro |
| 6–7 | coordenada X/Z |

Quanto **menor** o `max_chars`, **maior** a fonte naquele campo.

### 4. Criar o painel
Copiar `drill_panel.py` (é o mais simples) e trocar:
- `FIELDS` pela tabela medida;
- `TOGGLE` / toggles da operação;
- o aspect ratio no `ImageOverlayPanel(..., aspect=...)`;
- a faixa `_build_strip()` com o que **não** aparece no desenho
  (título, zero peça, fuso, refrigeração, velocidades, avanços);
- `operationType` no `collect()`.

Manter a interface: `changed` (signal), `collect()`, `load(params)`.

### 5. Registrar na aba
Em `tab.py`: importar o form, acrescentar em `OPS` e adicionar o `elif` no
`_build_ui` (junto de `FACE`/`DRILL`).

### 6. Verificar
```bash
# engine (paridade com o EvoCAM)
python3 -m pytest torno_cam/tests -q

# G-code gerado: validar no interpretador REAL do LinuxCNC
rs274 -g -i Dino_Evo.ini -t tool.tbl programa.ngc
```

---

## Armadilhas já pagas (não repetir)

### 1. O tema sobrepõe `setFont()` — foi o bug mais caro
`probe_basic_custom.qss` tem `VCPLineEdit, QLineEdit { font: 15pt "Bebas Kai"; }`.
**Folha de estilo da aplicação vence `setFont()`.** O tamanho calculado era
descartado e o número saía em 15pt na máquina.

→ A fonte vai na folha de estilo **do próprio widget** (`font-size: NNpx`),
que tem precedência. Ver `OverlayEdit.restyle()`.

### 2. Testar SEMPRE com o QSS carregado
Sem isso o teste mente — foi o que escondeu a armadilha 1 por várias rodadas:
```python
app.setStyleSheet(open("probe_basic_custom.qss").read())
```

### 3. Medir texto renderizado tem duas pegadinhas
- o **cursor** do QLineEdit é uma barra do tamanho da linha e conta como
  pixel claro → medir com `setReadOnly(True)`;
- a **borda desenhada** da caixa fica na aresta do widget → ou medir com
  margem, ou renderizar o campo isolado, sem imagem de fundo.

### 4. Vírgula decimal
Teclado BR manda vírgula; `QDoubleSpinBox` a recusa e `0,2` vira `2.0`.
Resolvido em `TouchDoubleSpin.validate()` e em `OverlayEdit` (converte ao vivo).

### 5. Ciclo fixo é dialeto, não estratégia
O pós do EvoCAM emite código inválido no LinuxCNC 2.9. As correções ficam em
`linuxcnc_dino.py`, nunca nas estratégias — assim a **paridade byte-a-byte**
com o engine original continua valendo (88 testes).

Corrigidos até agora: `G33` no lugar do `G32`; furação com `G17` (em `G18` o
ciclo furaria em **Y**, que não existe no torno); pausa em **segundos** (o IR
traz milissegundos); `G82` quando há pausa (`G81`/`G83` aceitam `P` e ignoram).
Desbaste (G71), canal (G75) e rosca (G76) seguem **bloqueados** até validar.

### 6. Resolução
Interface desenhada para **1920×1080**; os INIs abrem em `--fullscreen true`.
Os campos escalam com o painel — janela menor = fonte menor.

---

## Ajustes rápidos

| O quê | Onde |
|---|---|
| Tamanho geral dos números | `ESCALA_FONTE` em `image_panel.py` (0.80 = 80% do máximo que cabe) |
| Fonte usada | `NUM_FONT` em `image_panel.py` |
| Folga até o traço da caixa | parâmetro `folga` do `add_box_item()` |
| Diagnóstico de tamanho real | `torno_cam_diag.log` na raiz do config (gravado ao abrir a aba) |
