# Replicação do Estilo do Editor de G-Code (Probe Basic Lathe)

> **Objetivo:** este documento é um briefing autocontido para o Claude rodando em outra máquina (Linux real com LinuxCNC instalado). Lendo apenas este arquivo, o Claude deve conseguir localizar os arquivos certos, fazer as alterações certas, testar e reverter se necessário.

---

## 1. Contexto

- **Software:** [LinuxCNC](https://linuxcnc.org) + GUI **Probe Basic Lathe** (baseada em **QtPyVCP** / PyQt5).
- **Pacotes Debian envolvidos:** `qtpyvcp`, `probe-basic`, `probe-basic-lathe` (instalados em `/usr/lib/python3/dist-packages/...` em uma instalação padrão Debian/Ubuntu).
- **Tela alvo:** painel inferior do Probe Basic Lathe que exibe o programa NGC carregado (`GcodeEditor` contendo um `GcodeTextEdit`), com uma linha em destaque amarelo indicando a linha em execução (motion line).
- **Stack visual:**
  - Estilo geral (moldura, fonte do widget): **QSS** (Qt StyleSheet).
  - Cor de fundo do editor, fonte e foreground padrão: hardcoded em **Python** no widget.
  - Cor de fundo da linha ativa: **property no arquivo `.ui`** (`currentLineBackground`).
  - Cor do texto da linha ativa (amarelo): **hardcoded em Python** (`setForeground(QColor("#CCCC00"))`).
  - Syntax highlighting (G-codes, M-codes, eixos, comentários): **YAML** em `qtpyvcp/yaml_lib/gcode_syntax.yml`.

---

## 2. Arquivos-fonte que controlam o visual

Em uma instalação padrão (Debian/Ubuntu, pacote oficial QtPyVCP):

| Arquivo | O que controla |
|---|---|
| `/usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe.qss` | QSS global do Probe Basic Lathe (moldura do `GcodeEditor`, scrollbars, botões, etc.) |
| `/usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe.ui` | UI do app: define a `property currentLineBackground` do `GcodeTextEdit` |
| `/usr/lib/python3/dist-packages/qtpyvcp/widgets/input_widgets/gcode_text_edit.py` | Widget Python — define fonte, cor de fundo, cor padrão do texto e **cor amarela hardcoded da linha ativa** |
| `/usr/lib/python3/dist-packages/qtpyvcp/yaml_lib/gcode_syntax.yml` | Cores de syntax highlighting (G0, G1, M3, eixos X/Y/Z, comentários…) |
| `/usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe_original.qss` | Cópia original do QSS (fallback para restauração) |

Se algum desses caminhos não existir na máquina-alvo, localize com:

```bash
find /usr -path '*/probe_basic_lathe/*.qss' 2>/dev/null
find /usr -path '*/qtpyvcp/widgets/input_widgets/gcode_text_edit.py' 2>/dev/null
find /usr -name 'gcode_syntax.yml' 2>/dev/null
```

Se o usuário usar venv/conda, ajuste a busca para `$VIRTUAL_ENV` ou `~/.local/lib`.

---

## 3. Valores exatos do estilo atual (lidos do código-fonte)

### 3.1 Widget do editor (`GcodeTextEdit`, em `gcode_text_edit.py` linhas 149-160 e 575)

```python
# Fonte
_font = QFont("Liberation Sans Narrow", 22)
_font.setBold(False)
_font.setWeight(QFont.Light)

# Cores via palette
palette.setColor(palette.Base, QColor("#2A2A2A"))   # fundo do editor
palette.setColor(palette.Text, QColor("#FFFFFF"))   # texto padrão

# Foreground da linha ativa (em motion) — HARDCODED no onCursorChanged
selection.format.setForeground(QColor("#CCCC00"))   # AMARELO
```

### 3.2 Fundo da linha ativa (`probe_basic_lathe.ui`, property do widget)

```xml
<property name="currentLineBackground" stdset="0">
  <color>
    <red>30</red>
    <green>30</green>
    <blue>30</blue>
  </color>
</property>
```
→ Equivale a `#1E1E1E`.

### 3.3 QSS — moldura e fontes (`probe_basic_lathe.qss` linhas 121-144)

```qss
GcodeBackplot {
    border-color: black;
    border-style: solid;
    border-width: 2px;
    border-radius: 4px;
    background-color: black;
    margin: 10px;
    font: 12pt "Bebas Kai";
}

GcodeEditor {
    background-color: white;
    border-color: black;
    border-style: solid;
    border-width: 2px;
    border-radius: 4px;
    padding: 2px;
    font: 12pt "Bebas Kai";
}

GcodeTextEdit {
    background-color: #2A2A2A;
    font: 22pt "Liberation Sans Narrow";
}
```

### 3.4 Tabela consolidada

| Elemento | Valor atual | Onde está definido |
|---|---|---|
| Fundo do editor | `#2A2A2A` | `gcode_text_edit.py:158` + QSS `GcodeTextEdit` |
| Texto padrão | `#FFFFFF` | `gcode_text_edit.py:159` |
| Fonte do editor | `Liberation Sans Narrow`, 22pt, Light | `gcode_text_edit.py:150-152` + QSS |
| Fonte do `GcodeEditor` (moldura) | `Bebas Kai`, 12pt | QSS `GcodeEditor` |
| Fundo da linha ativa | `#1E1E1E` (rgb 30,30,30) | `probe_basic_lathe.ui` property `currentLineBackground` |
| Texto da linha ativa | `#CCCC00` (amarelo) | `gcode_text_edit.py:575` **(hardcoded)** |
| Borda do `GcodeEditor` | preto, 2px, raio 4px | QSS |
| Cores de syntax (M-codes, eixos, comentários, etc.) | ver `gcode_syntax.yml` | `qtpyvcp/yaml_lib/gcode_syntax.yml` |

---

## 4. Hierarquia de widgets (importante para customizar via QSS)

```
QMainWindow
└── ... várias tabs ...
    └── GcodeEditor                  ← moldura branca com border preto
        ├── ToolBar (botões find/replace, etc.)
        └── GcodeTextEdit            ← área escura com o texto NGC
            └── NumberMargin         ← coluna dos números de linha
```

Seletores QSS úteis:
- `GcodeEditor { ... }` — moldura geral
- `GcodeTextEdit { ... }` — área de texto (fundo, fonte)
- `GcodeBackplot { ... }` — visualização gráfica do toolpath (não é o editor de texto)

---

## 5. Procedimento de customização (passo a passo)

### Pré-requisitos

- Acesso `sudo` (os arquivos estão em `/usr/lib/...`).
- Permissão do usuário para reiniciar o LinuxCNC/Probe Basic.

### 5.1 Backup obrigatório

Antes de qualquer edição:

```bash
sudo cp /usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe.qss \
        /usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe.qss.bak.$(date +%F)

sudo cp /usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe.ui \
        /usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe.ui.bak.$(date +%F)

sudo cp /usr/lib/python3/dist-packages/qtpyvcp/widgets/input_widgets/gcode_text_edit.py \
        /usr/lib/python3/dist-packages/qtpyvcp/widgets/input_widgets/gcode_text_edit.py.bak.$(date +%F)
```

### 5.2 Alterações por objetivo

**Mudar fonte/cor de fundo do editor** → edite o QSS:

```qss
GcodeTextEdit {
    background-color: #2A2A2A;            /* novo fundo */
    color: #FFFFFF;                       /* novo texto padrão */
    font: 22pt "Liberation Sans Narrow";  /* nova fonte */
}
```

E em `gcode_text_edit.py` linhas 150-159 — alterar a fonte e o palette também (o QSS sozinho não sobrescreve o palette do Qt em todos os casos; mexa nos dois para ficar consistente).

**Mudar a cor da linha ativa (background)** → edite a property em `probe_basic_lathe.ui`:

```xml
<property name="currentLineBackground" stdset="0">
  <color>
    <red>58</red>
    <green>58</green>
    <blue>42</blue>
  </color>
</property>
```

**Mudar a cor amarela do texto da linha ativa** → edite `gcode_text_edit.py` linha 575:

```python
selection.format.setForeground(QColor("#CCCC00"))   # trocar pelo hex desejado
```

> Esta cor é **hardcoded**. Não há como mudar só via QSS ou .ui — precisa editar Python.

**Mudar cores de syntax (G-code, M-code, eixos)** → edite `gcode_syntax.yml`. Cada bloco tem um `foreground: '#RRGGBB'`.

### 5.3 Reiniciar para ver as mudanças

Probe Basic não tem hot-reload de QSS/UI. Feche e reabra:

```bash
# fecha qualquer instância
pkill -f probe_basic_lathe || true
# inicia com a config do usuário
linuxcnc /home/eds/linuxcnc/configs/Dino_Evo/probe_basic_lathe.ini
```

Substitua o `.ini` pelo path real da config se for outra máquina (procurar com `ls ~/linuxcnc/configs/`).

### 5.4 Verificação visual

Carregue um programa NGC (ex.: `~/linuxcnc/nc_files/pb_examples/blank.ngc`) e confirme:

1. Fundo do editor é o cinza escolhido.
2. Texto padrão na cor escolhida.
3. Ao executar (ou ao clicar numa linha), a linha ativa mostra fundo + texto na nova combinação.
4. Números de linha continuam legíveis.
5. Os botões `GCODE`/`MDI`/`RUN FROM LINE` não regrediram (caso o QSS deles tenha sido tocado por engano).

### 5.5 Restauração

Se algo ficar ruim:

```bash
sudo cp /usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe.qss.bak.YYYY-MM-DD \
        /usr/lib/python3/dist-packages/probe_basic_lathe/probe_basic_lathe.qss
# idem para os outros arquivos
```

Ou use o `probe_basic_lathe_original.qss` que já vem com o pacote como referência limpa.

---

## 6. Especificação visual de referência (caso vá replicar em outra stack)

> Estes são os valores observados no screenshot original e que devem ser reproduzidos. Se a máquina-alvo já usa exatamente o Probe Basic Lathe não modificado, os valores das seções anteriores **já produzem este resultado** — nada precisa ser feito.

### 6.1 Paleta

| Elemento | HEX | RGB | Origem |
|---|---|---|---|
| Fundo do editor | `#2A2A2A` | 42,42,42 | `gcode_text_edit.py` |
| Fundo da linha ativa | `#1E1E1E` | 30,30,30 | `.ui` property |
| Texto padrão | `#FFFFFF` | 255,255,255 | `gcode_text_edit.py` |
| Texto da linha ativa | `#CCCC00` | 204,204,0 | `gcode_text_edit.py` (hardcoded) |
| Comentários `(...)` | `gray` | — | `gcode_syntax.yml` (itálico) |
| Eixo X | `#76AF00` | — | `gcode_syntax.yml` |
| Eixo Z | `#E24E29` | — | `gcode_syntax.yml` |
| M-codes | `#FF4500` | — | `gcode_syntax.yml` |
| Botão GCODE ativo | `#C8732E` (laranja queimado) | aprox. | QSS principal |

### 6.2 Fonte

- **Família principal do editor:** `Liberation Sans Narrow` (proporcional, condensada).
- **Tamanho:** 22pt.
- **Peso:** Light (`QFont.Light`) — **não** é negrito apesar de parecer denso por causa do tamanho.
- **Família da moldura/botões:** `Bebas Kai` em 12pt.
- **Antialiasing:** ligado (padrão do Qt no Linux).

Se essas fontes não estiverem instaladas, instalar:

```bash
sudo apt install fonts-liberation
# Bebas Kai não está nos repos padrão — geralmente vem com o pacote probe-basic;
# fallback aceitável: "DejaVu Sans Condensed" ou "Roboto Condensed".
```

Verificar instalação:

```bash
fc-list | grep -iE "liberation sans narrow|bebas"
```

### 6.3 Layout (proporções observadas)

- Altura da linha: ~32 px (com fonte 22pt Light).
- Margem da coluna de números: ~12 px após o número.
- Padding interno do editor: 2 px (definido no QSS `GcodeEditor`).
- Borda do `GcodeEditor`: 2 px preto, raio 4 px.

---

## 7. Caminhos alternativos (se editar `/usr/lib` for inviável)

Se não quiser mexer em arquivos de sistema (preferível em ambiente de produção):

### Opção A — QSS local na config do usuário

QtPyVCP permite stylesheet por aplicação via INI. No `probe_basic_lathe.ini`:

```ini
[DISPLAY]
STYLESHEET = custom_gcode_style.qss
```

E criar `custom_gcode_style.qss` no mesmo diretório do INI:

```qss
GcodeTextEdit {
    background-color: #2A2A2A;
    color: #FFFFFF;
    font: 22pt "Liberation Sans Narrow";
}
GcodeEditor {
    border: 2px solid black;
    border-radius: 4px;
}
```

**Limitação:** o QSS local NÃO consegue alterar o `#CCCC00` da linha ativa nem o `currentLineBackground` do `.ui` — esses só por edição dos arquivos do pacote ou subclasse Python.

### Opção B — Subclasse Python no diretório do usuário

Criar um widget customizado que herda de `GcodeTextEdit` e sobrescreve `onCursorChanged` com cor diferente, depois registrar no `.ui` local. Mais invasivo — só recomendar se o usuário pedir explicitamente.

---

## 8. Checklist antes de reportar "feito"

- [ ] Backups foram criados com `.bak.<data>`.
- [ ] Caminhos no `/usr/lib/...` correspondem à máquina-alvo (validados via `find`).
- [ ] As fontes `Liberation Sans Narrow` e (se possível) `Bebas Kai` estão instaladas.
- [ ] Probe Basic Lathe foi reiniciado após as edições.
- [ ] Programa NGC de exemplo carrega sem erros.
- [ ] Linha ativa exibe a combinação fundo/texto esperada ao executar.
- [ ] Nenhuma regressão visual em outros widgets (DRO, tool table, backplot).
- [ ] Caminho de rollback documentado para o usuário.

---

## 9. Resumo executivo (TL;DR para o Claude)

Para reproduzir EXATAMENTE o visual do screenshot referência:
1. Confirme que está em uma instalação Probe Basic Lathe padrão (`/usr/lib/python3/dist-packages/probe_basic_lathe/` existe).
2. Os valores já são os do pacote oficial — nada precisa ser alterado para ter este look.
3. Se a máquina-alvo já estiver com customizações, comparar os 3 arquivos (`probe_basic_lathe.qss`, `probe_basic_lathe.ui`, `gcode_text_edit.py`) contra os valores da Seção 3 e ajustar.
4. Instalar as fontes `fonts-liberation` se faltarem.
5. Reiniciar com `linuxcnc <caminho>/probe_basic_lathe.ini`.

Se o usuário quiser **modificar** o visual (não apenas replicar), use a Seção 5 como guia e sempre faça backup antes.
