# HAL - Spindle com Inversor CFW-07

## Arquitetura

```
LinuxCNC                    Mesa/BOB                 Reles           CFW-07
=========                   ========                 =====           ======
spindle.0.speed-out         
  -> PID -> spindle-output  
    -> pwmgen.00 (0-10V) ──────────── direto ────────────────── AI1 (borne 02)
                            GND ────── direto ────────────────── AGND (borne 04)

spindle.0.on                
  -> spindle-enable         
    -> timedelay (off-delay=5s)
      -> spindle-enable-delayed
        -> pwmgen.01 enable ── PWM1 ──► Rele1 NA ──► 0V ─────── DI1 (borne 09)
                                        coil 24V      borne 08

spindle.0.reverse           
  -> spindle-ccw            
    -> pwmgen.02 enable ───── PWM2 ──► Rele2 NA ──► 0V ──────── DI2 (borne 10)
                                       coil 24V      borne 08

                            Jumper fixo: borne 12 ──── borne 08   DI4 (rampa)
```

## Codigo HAL (Dino_Evo.hal)

### Velocidade (PWM0 -> AI1)
```hal
setp hm2_7i92.0.pwmgen.00.output-type 1
setp hm2_7i92.0.pwmgen.00.scale 1700
net spindle-output => hm2_7i92.0.pwmgen.00.value
net spindle-enable => hm2_7i92.0.pwmgen.00.enable
```

### Enable com timer de frenagem (PWM1 -> Rele -> DI1)
```hal
# Timer mantem DI1 ativo por 5s apos M5 para rampa + frenagem CC
setp timedelay.spindle-enable.on-delay  0
setp timedelay.spindle-enable.off-delay 5
net spindle-enable => timedelay.spindle-enable.in
net spindle-enable-delayed timedelay.spindle-enable.out
setp hm2_7i92.0.pwmgen.01.output-type 1
setp hm2_7i92.0.pwmgen.01.scale 1
setp hm2_7i92.0.pwmgen.01.value 1
net spindle-enable-delayed => hm2_7i92.0.pwmgen.01.enable
```

### Direcao (PWM2 -> Rele -> DI2)
```hal
setp hm2_7i92.0.pwmgen.02.output-type 1
setp hm2_7i92.0.pwmgen.02.scale 1
setp hm2_7i92.0.pwmgen.02.value 1
net spindle-ccw => hm2_7i92.0.pwmgen.02.enable
```

### Encoder feedback
```hal
setp hm2_7i92.0.encoder.00.scale 400
net spindle-revs       <= hm2_7i92.0.encoder.00.position
net spindle-vel-fb-rps <= hm2_7i92.0.encoder.00.velocity
net spindle-vel-fb-rpm <= hm2_7i92.0.encoder.00.velocity-rpm
```

## Tabela de Comandos G-code

| Comando | Acao | PWM0 | PWM1 (DI1) | PWM2 (DI2) |
|---------|------|------|------------|------------|
| M3 S1000 | CW 1000rpm | proporcional | ON (habilitado) | OFF (horario) |
| M4 S500 | CCW 500rpm | proporcional | ON (habilitado) | ON (anti-horario) |
| M5 | Parar | 0V | ON 5s (timer frenagem) | OFF |

## Ver tambem
- [[03 - Inversor CFW-07]]
- [[20 - Parametros CFW-07]]
