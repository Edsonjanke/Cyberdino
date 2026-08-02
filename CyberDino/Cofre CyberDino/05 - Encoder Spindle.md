# Encoder Spindle

## Especificacoes
- Encoder hardware da Mesa 7i92 (encoder.00)
- **400 PPR** (pulsos por revolucao)
- Sem Index Z (limitacao do firmware)
- Conectado via DB15 (P1)

## Pinagem DB15
| Pino DB15 | I/O Mesa | Funcao |
|-----------|----------|--------|
| 3 | I/O 18 | encoder.00.B (fase B) |
| 4 | I/O 17 | encoder.00.A (fase A) |
| 14 | - | GND |

## Configuracao HAL
```
setp hm2_7i92.0.encoder.00.counter-mode 0
setp hm2_7i92.0.encoder.00.filter 1
setp hm2_7i92.0.encoder.00.scale 400
```

## Sinais
- `spindle-revs` <- encoder position (revolucoes)
- `spindle-vel-fb-rps` <- encoder velocity (RPS)
- `spindle-vel-fb-rpm` <- encoder velocity (RPM)
- `spindle-index-enable` <=> index enable (threading)

## Status
Funcionando desde 2026-04-06.
