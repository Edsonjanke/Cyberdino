# Parametros CFW-07 - Configuracao CNC

## Sequencia de Programacao

### 1. Restaurar padrao fabrica
```
P204 = 5    (carrega padrao)
```

### 2. Dados do inversor e motor
| Param | Funcao | Valor | Nota |
|-------|--------|-------|------|
| P296 | Tensao nominal | **1** | 380V |
| P295 | Corrente inversor | **108** | 16A |
| P401 | Corrente motor | **1.0** | 12A (nominal do motor) |
| P202 | Tipo controle | **0** | U/F 60Hz |

### 3. Operacao REMOTO (via bornes)
| Param | Funcao | Valor | Nota |
|-------|--------|-------|------|
| P220 | Sel. LOCAL/REMOTO | **1** | Sempre REMOTO |
| P222 | Ref. REMOTO | **1** | AI1 (0-10V) |
| P226 | Sentido giro REMOTO | **3** | DI2 |
| P227 | Liga/Desliga REMOTO | **1** | Inativo (controlado por DI1) |

### 4. Rampa
| Param | Funcao | Valor | Nota |
|-------|--------|-------|------|
| P100 | Aceleracao | **3.0** s | |
| P101 | Desaceleracao | **2.0** s | Rapida c/ resistor frenagem |

### 4b. Frenagem CC (parada final)
| Param | Funcao | Valor | Nota |
|-------|--------|-------|------|
| P300 | Duracao frenagem CC | **1.5** s | Trava eixo no final |
| P301 | Freq. inicio frenagem CC | **1.0** Hz | Inicio da injecao CC |
| P302 | Tensao CC frenagem | **4.0** % | Torque de frenagem (% Vnom) |

### 5. Ganho entrada analogica
| Param | Funcao | Valor | Nota |
|-------|--------|-------|------|
| P234 | Ganho AI1 | **1.50** | Compensa saida analogica da placa (~6.7V max) |

### 6. Limites de frequencia
| Param | Funcao | Valor |
|-------|--------|-------|
| P133 | Freq minima | **3.0** Hz |
| P134 | Freq maxima | **60.0** Hz |

## Parametros de Leitura (monitoramento)
| Param | Funcao |
|-------|--------|
| P002 | Valor proporcional a freq (P208 x P005) |
| P003 | Corrente do motor |
| P004 | Tensao CC |
| P005 | Frequencia aplicada ao motor |
| P007 | Tensao de saida |
| P023 | Versao de software |

## Mensagens de Erro
| Codigo | Significado |
|--------|-------------|
| E00 | Sobrecorrente / curto-circuito saida |
| E01 | Sobretensao CC |
| E02 | Subtensao CC |
| E04 | Sobretemperatura |
| E05 | Sobrecarga (I x t) |
| E06 | Erro externo |
| E11 | Curto fase-terra |
| E24 | Erro de parametrizacao |

## Estados do Display
| Estado | Significado |
|--------|-------------|
| rdy | Pronto para operar |
| Sub | Subtensao - desabilitado |

## Funcoes das Entradas Digitais (padrao fabrica)
| DI | Param | Funcao Padrao |
|----|-------|---------------|
| DI1 | - | Habilita Geral |
| DI2 | P264 | Sentido de Giro |
| DI3 | P265 | Local/Remoto |
| DI4 | P266 | Habilita Rampa |
