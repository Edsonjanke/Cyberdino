# Chave Seletora de Modo

## Funcionamento
Chave fisica com 3 posicoes (2 GPIOs, 3 modos):

| GPIO.024 | GPIO.023 | Modo |
|----------|----------|------|
| GND | - | AUTO |
| - | GND | MDI |
| Solto | Solto | JOG (manual) |

## Interlock
- Programa para automaticamente se chave nao esta em AUTO
- ProbeBasic pode forcar modo AUTO via NML (software), por isso o interlock e necessario

## Interface ProbeBasic
- Botoes MAN/AUTO/MDI trocados de ActionButton para `ReadOnlyAction`
- Nao sao clicaveis (so indicador visual controlado pela chave fisica)
- Widget em `mpg_button.py` (classe ReadOnlyAction)

## Status
Configurado desde 2026-04-06. Soldado na placa e testado.
