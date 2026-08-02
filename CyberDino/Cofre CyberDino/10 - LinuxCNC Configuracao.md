# LinuxCNC - Configuracao

## Versao
- LinuxCNC 2.9.7 (Master)
- ProbeBasic Lathe 0.6.6
- QtPyVCP 5.1.0

## Tipo de Maquina
- **Back Tool Lathe** (torno com ferramenta atras)
- 2 eixos: X, Z
- Steppers closed-loop via PID

## Arquivos Principais
| Arquivo | Funcao |
|---------|--------|
| `Dino_Evo.ini` | Configuracao principal |
| `Dino_Evo.hal` | HAL principal (eixos, spindle, GPIOs) |
| `custom.hal` | E-Stop, MPG, chave seletora |
| `probe_basic_postgui_fix.hal` | Conexoes pos-GUI (indicadores) |
| `probe_basic_custom.ui` | Interface customizada |
| `probe_basic_custom.qss` | Estilo customizado (tema cobre) |
| `custom_config.yml` | Referencia UI e QSS customizados |

## Configuracoes INI Importantes
```ini
[DISPLAY]
DEFAULT_SPINDLE_SPEED = 300
MAX_SPINDLE_OVERRIDE = 2.000000
MIN_SPINDLE_OVERRIDE = 0.500000

[TRAJ]
SPINDLES = 1

[SPINDLE_0]
FF0 = 1
MAX_OUTPUT = 1700
ENCODER_SCALE = 400
```

## Incrementos de Jog
`1mm .5mm .1mm .05mm .01mm` (removidos 5mm e .005mm)
