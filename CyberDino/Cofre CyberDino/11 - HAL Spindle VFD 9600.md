# HAL - Spindle com Inversor VFD 9600

**Substituiu CFW-07 em 2026-04-23.**

## Arquitetura

```
LinuxCNC                    Mesa/BOB                 Reles           VFD 9600
=========                   ========                 =====           ========
spindle.0.speed-out
  -> PID (FF0=1) -> spindle-output
    -> pwmgen.00 (0-10V filtrado) ────────── direto ────────── AI1
                            GND (ACOM) ────── direto ────────── GND analog

spindle.0.forward (M3)
  -> spindle-cw
    -> pwmgen.01 enable (como digital) ─── PWM1 ──► Rele1 NA ──► X1 (FWD)

spindle.0.reverse (M4)
  -> spindle-ccw
    -> pwmgen.02 enable (como digital) ─── PWM2 ──► Rele2 NA ──► X2 (REV)

                                Comum reles ──────────────────► DCOM
                                Jumper OP-24V fechado (default)
```

## Codigo HAL (Dino_Evo.hal)

### Velocidade (PWM0 -> AI1)
```hal
setp hm2_7i92.0.pwmgen.00.output-type 1
setp hm2_7i92.0.pwmgen.00.scale 2975     # calibrado empiricamente (2x teorico porque BOB dobra voltagem)
net spindle-output => hm2_7i92.0.pwmgen.00.value
net spindle-enable => hm2_7i92.0.pwmgen.00.enable
```

### FWD (PWM1 -> Rele -> X1)
Two-line mode 1: X1 ativa so em M3.
```hal
setp hm2_7i92.0.pwmgen.01.output-type 1
setp hm2_7i92.0.pwmgen.01.scale 1
setp hm2_7i92.0.pwmgen.01.value 1
net spindle-cw => hm2_7i92.0.pwmgen.01.enable
```

### REV (PWM2 -> Rele -> X2)
X2 ativa so em M4.
```hal
setp hm2_7i92.0.pwmgen.02.output-type 1
setp hm2_7i92.0.pwmgen.02.scale 1
setp hm2_7i92.0.pwmgen.02.value 1
net spindle-ccw => hm2_7i92.0.pwmgen.02.enable
```

### Encoder feedback com lowpass
```hal
loadrt lowpass names=lowpass.spindle,lowpass.spindle-rps
addf lowpass.spindle-rps servo-thread

setp hm2_7i92.0.encoder.00.counter-mode 0
setp hm2_7i92.0.encoder.00.filter 1
setp hm2_7i92.0.encoder.00.scale [SPINDLE_0]ENCODER_SCALE  # 400

net spindle-revs         <= hm2_7i92.0.encoder.00.position
net spindle-index-enable <=> hm2_7i92.0.encoder.00.index-enable

# 1a etapa: lowpass no feedback RPS (afeta PID/at-speed/display)
# gain 0.02 @ 1ms servo = ~50ms TC
setp lowpass.spindle-rps.gain 0.02
net spindle-vel-fb-rps-raw <= hm2_7i92.0.encoder.00.velocity
net spindle-vel-fb-rps-raw => lowpass.spindle-rps.in
net spindle-vel-fb-rps     <= lowpass.spindle-rps.out
net spindle-vel-fb-rpm     <= hm2_7i92.0.encoder.00.velocity-rpm
```

### Cadeia de display (scale + abs + lowpass dedicado)
Sinal consumido pelo DRO do Probe Basic: `spindle-fb-rpm-abs-filtered`.
```hal
setp scale.spindle.gain    60          # RPS -> RPM
setp lowpass.spindle.gain  0.05        # ~20ms TC EXTRA so no display (2026-04-24)
net spindle-vel-fb-rps          => scale.spindle.in
net spindle-fb-rpm               scale.spindle.out  => abs.spindle.in
net spindle-fb-rpm-abs           abs.spindle.out    => lowpass.spindle.in
net spindle-fb-rpm-abs-filtered  lowpass.spindle.out
```
**Nota:** gain original era 1.0 (sem filtrar). Abaixado para 0.05 para estabilizar display sem impactar at-speed nem PID. Se ainda oscilar, baixar para 0.02 (~50ms TC).

### At-speed (near.spindle)
Trava motion: eixos so avancam apos `spindle.0.at-speed=TRUE`. Formula:
`at-speed = TRUE quando |cmd - fb| <= max(difference, scale * |cmd|)`

```hal
# (2026-04-24) scale 1.5 era 150% — sempre TRUE, motion nao esperava
setp near.spindle.scale      0.05      # 5% relativo
setp near.spindle.difference 0.5       # piso 0.5 RPS = 30 RPM (protege RPM baixo)
net spindle-vel-cmd-rps-abs => near.spindle.in1
net spindle-vel-fb-rps      => near.spindle.in2
net spindle-at-speed        <= near.spindle.out
net spindle-at-speed        => spindle.0.at-speed
```
Exemplo: M3 S1500 → VFD rampeia 6s (P0-17) → at-speed vira TRUE em ~1425 RPM → G1 libera.

## Tabela de Comandos G-code

| Comando | Acao | PWM0 | PWM1 (X1) | PWM2 (X2) |
|---------|------|------|-----------|-----------|
| M3 S1000 | CW 1000rpm | proporcional (~3.4V) | ON | OFF |
| M4 S500 | CCW 500rpm | proporcional (~1.7V) | OFF | ON |
| M5 | Parar | 0V | OFF | OFF |

Rampa de parada: controlada por P0-18 do VFD (10s), nao por timer HAL.

## Diferencas para CFW-07

| Aspecto | CFW-07 (antigo) | VFD 9600 (atual) |
|---|---|---|
| Rele 1 | Enable (habilita geral) | FWD (M3) |
| Rele 2 | Sentido (M4 fecha, M3 abre) | REV (M4) |
| Timer HAL | timedelay 5s para frenagem DC | Removido (VFD faz rampa interna) |
| Modo VFD | Nao aplicavel | P4-11=0 (two-line mode 1) |
| pwmgen.00 scale | 1700 | 2975 (calibrado) |
| Enable logic | Ativo M3 E M4 | Mutuamente exclusivo |

## Valores INI [SPINDLE_0]

```ini
[SPINDLE_0]
P = 0
I = 0
D = 0
FF0 = 1
FF1 = 0
FF2 = 0
BIAS = 0
DEADBAND = 0
MAX_OUTPUT = 2975
ENCODER_SCALE = 400
```

PID em modo pure feedforward (FF0=1). Considerar habilitar P/I para compensar nao-linearidade se necessario.

## Ver tambem
- [[03 - Inversor VFD 9600]]
- [[20 - Parametros VFD 9600]]
- [[05 - Encoder Spindle]]
