# MPG Handwheel

## Hardware
- Encoder diferencial (A/B/-A/-B), so A/B ligados
- Software encoder no LinuxCNC (`loadrt encoder` no custom.hal)
- Escala: 0.01mm por click

## Pinagem
| GPIO | I/O | Funcao | DB15 Pino |
|------|-----|--------|-----------|
| GPIO.030 | IN | Fase A | 10 |
| GPIO.031 | IN | Fase B | 7 |
| GPIO.027 | IN | Chave Enable | - |
| GPIO.025 | IN | Chave X/Z | - |

## Chaves
- **Enable** (GPIO.027): liga/desliga MPG
- **X/Z** (GPIO.025): OFF = eixo X, ON = eixo Z

## Interface ProbeBasic
- Widget `MpgButton` em `mpg_button.py` (indicador visual read-only)
- Pin HAL: `qtpyvcp.mpg-indicator.in`
- Conexao: `net mpg-enabled => qtpyvcp.mpg-indicator.in`

## Status
Funcionando desde 2026-04-06.
