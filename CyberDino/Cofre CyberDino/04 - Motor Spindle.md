# Motor Spindle

## Dados do Motor
| Dado | Valor |
|------|-------|
| **Potencia** | 7.5 CV (5.5 kW) |
| **Tensao** | 380V trifasico |
| **Corrente nominal** | 12A |
| **RPM nominal** | ~1700 RPM (a 60Hz) |

## Conexao
- Alimentado pelo inversor [[03 - Inversor CFW-07]] (bornes U, V, W)
- Encoder acoplado no eixo: [[05 - Encoder Spindle]]

## Protecao
- P401 (corrente nominal motor no CFW-07) = 1.0 x Inom = 12A
- Inversor tem protecao eletronica de sobrecarga (P156, P169)
