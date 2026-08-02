# ProbeBasic - Interface Customizada

## Arquivos
| Arquivo | Local | Funcao |
|---------|-------|--------|
| `probe_basic_custom.ui` | configs/Dino_Evo/ | UI customizado (copia editada do lathe original) |
| `probe_basic_custom.qss` | configs/Dino_Evo/ | Estilo customizado |
| `custom_config.yml` | configs/Dino_Evo/ | Referencia ui_file e stylesheet |
| `mpg_button.py` | `~/.local/lib/python3.11/site-packages/` | Widgets custom |

## Widgets Customizados (mpg_button.py)

### MpgButton
- Indicador MPG read-only
- Pin HAL `.in` controla `setChecked`
- Mouse bloqueado (nao clicavel)

### ReadOnlyAction
- Indicador de modo (MAN/AUTO/MDI)
- Usa `bindWidget` para acompanhar action
- Mouse bloqueado (controlado pela chave fisica)

## Tema Cobre
Cor azul original trocada para cobre vivo em toda interface:
- Gradiente: `rgba(218,135,40)` / `rgba(204,120,30)` / `rgba(184,100,15)`
- Botao POWER: letra preta (`color: black`)

## Licoes Aprendidas
- QtPyVCP so carrega **1 POSTGUI_HALFILE** (usa `ini.find`, nao `findall`)
- QtPyVCP pins HAL usam **hifen** (nao underscore): `qtpyvcp.mpg-indicator.in`
- Widget name no Qt = `mpg_indicator`, pin HAL = `mpg-indicator`
- HalButton ignora `.in` pin se mouse clicar; usar widget custom read-only
