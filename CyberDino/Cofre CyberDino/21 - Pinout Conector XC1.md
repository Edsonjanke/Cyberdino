# Pinout Conector XC1 - CFW-07

Referencia: Manual CFW-07, Figura 3.5 (paginas 27-28)

## Esquema Completo

```
        XC1 (Cartao CEC8)
        ==================

 ANALOGICO:
  01 ──── +10V (fonte interna, max 20mA)
  02 ──── AI1+ (CW) ──── entrada 0-10V referencia velocidade
  03 ──── AI1- (CCW) ──── entrada diferencial (nao usada)
  04 ──── 0V (AGND) ──── ground analogico

  05 ──── AI2+ ──── entrada analogica 2 (0-10V)
  06 ──── AI2- ──── (nao usada)

  07 ──── AO1 ──── saida analogica 0-10V (freq/corrente, conf P251)
  08 ──── 0V (DGND) ──── ground digital

 DIGITAL:
  09 ──── DI1 ──── Habilita Geral (NPN, ativo em 0V)
  10 ──── DI2 ──── Sentido de Giro (NPN, ativo=CCW, inativo=CW)
  11 ──── DI3 ──── Local/Remoto
  12 ──── DI4 ──── Habilita Rampa

 RELES:
  13 ──── RL1 Comum
  14 ──── RL1 NA ──── Fs > Fx (freq atingida)
  15 ──── RL2 Comum
  16 ──── RL2 NA ──── Sem Erro
```

## Caracteristicas das Entradas Digitais
- Nivel ALTO: > 5V ate +15Vcc
- Nivel BAIXO: < 0.5V
- Pull-up interno: +12V via 6K8 ohm
- Corrente: ~12mA quando ativo
- Ativacao: conectar ao 0V (borne 08)

## Jumper XJ1 (Selecao AI1)
| Posicao | Sinal AI1 |
|---------|-----------|
| 2-3 | 0 a 10V (padrao fabrica) |
| 1-2 | 0/4 a 20mA |

## Reles de Saida
- RL1: funcao conf P277 (padrao: Fs > Fx)
- RL2: sem erro (fixo)
- Capacidade contatos: 1A / 250Vac
