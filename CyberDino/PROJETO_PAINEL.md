# Projeto CyberDino - Painel de Comando Torno CNC

## Status: ENCODER SPINDLE FUNCIONANDO - Proximo: MPG ou PLC
**Ultima atualizacao:** 2026-04-06

---

## 1. Visao Geral

Retrofit de torno convencional para CNC usando LinuxCNC + ProbeBasic.
Objetivo: painel de comando fisico com feed override, spindle override, botoes e LEDs.

**Maquina:** Dino Evo
**GUI:** ProbeBasic Lathe (QtPyVCP)
**SO:** Debian 12 (Bookworm), kernel 6.1 PREEMPT_RT
**LinuxCNC:** 2.9.7 (uspace)
**CPU:** Intel i3-2120 @ 3.30GHz
**Tipo:** Torno (LATHE) - 2 eixos (X, Z) - Back Tool Lathe
**Local:** Evo (oficina)
**Pasta config Windows:** `G:\CyberDino\Linuxcnc\`
**Pasta config Linux:** `/home/evo/linuxcnc/configs/Dino_Evo/`
**Usuario Linux:** evo
**Hostname:** 192

---

## 2. Hardware

### 2.1 Mesa 7i92 - Placa Integrada V1.0

- Placa chinesa integrada (7i92 + BOB na mesma PCB, NAO e 7i92 pura)
- Ethernet IP `10.10.10.10`
- Firmware atual: `7i92_5ABOB_Enc.bit`

**Limitacao confirmada do firmware:**
- `num_encoders` maximo = **1** (tentou 2, erro: "only 1 are available")
- `num_pwmgens` maximo = 3
- `num_stepgens` maximo = 5
- **NAO tem Index (Z) no encoder** - so Quad-A e Quad-B

**Config atual funcionando:**
```
config="num_encoders=1 num_pwmgens=3 num_stepgens=5"
```

### 2.2 READHMID - Mapa Real de Pinos do FPGA

```
P2 (conector 1 - bornes steppers e PWM na placa)
DB25 pin  I/O   Funcao          Canal
 1         0    PWM              0        PWM (Spindle speed)
14         1    PWM              1        PWM (Coolant)
 2         2    StepGen          0        Step (Eixo X)
15         3    PWM              2        PWM (spare)
 3         4    StepGen          0        Dir  (Eixo X)
16         5    StepGen          4        Step (nao usado)
 4         6    StepGen          1        Step (Eixo Z)
17         7    StepGen          4        Dir  (nao usado)
 5         8    StepGen          1        Dir  (Eixo Z)
 6         9    StepGen          2        Step (nao usado)
 7        10    StepGen          2        Dir  (nao usado)
 8        11    StepGen          3        Step (nao usado)
 9        12    StepGen          3        Dir  (nao usado)
10        13    GPIO             -        gpio.013 (Spindle CW)
11        14    GPIO             -        gpio.014
12        15    GPIO             -        gpio.015
13        16    GPIO             -        gpio.016

P1 (conector 2 - DB15, encoder, GPIOs na placa)
DB25 pin  I/O   Funcao          Canal
 1        17    QCount           0        Quad-A  (ENCODER A)
14        18    QCount           0        Quad-B  (ENCODER B)
 2        19    GPIO             -        gpio.019 (E-Stop)
15        20    GPIO             -        gpio.020
 3        21    GPIO             -        gpio.021
16        22    GPIO             -        gpio.022
 4        23    GPIO             -        gpio.023
17        24    GPIO             -        gpio.024
 5        25    GPIO             -        gpio.025
 6        26    GPIO             -        gpio.026
 7        27    GPIO             -        gpio.027
 8        28    GPIO             -        gpio.028
 9        29    GPIO             -        gpio.029
10        30    GPIO             -        gpio.030
11        31    GPIO             -        gpio.031
12        32    GPIO             -        gpio.032
13        33    GPIO             -        gpio.033
```

**DESCOBERTA CRITICA:**
- encoder.00.A = I/O 17 = P1 pino 1
- encoder.00.B = I/O 18 = P1 pino 14
- NAO ha Index (Z) no firmware
- O borne fisico de encoder na placa pode NAO estar ligado a estes pinos

### 2.3 DB15 Handwheel - Pinagem Confirmada

(Fonte: imagem 手轮针脚定义.png - pinagem real da placa)

| Pino DB15 | Funcao | GPIO (I/O) |
|-----------|--------|------------|
| 1 | Eixo 4 | - |
| 2 | Escala x1 | gpio.016 (I/O 16?) |
| 3 | Encoder B (pulso B) | a confirmar |
| 4 | Encoder A (pulso A) | a confirmar |
| 5 | Escala x10 | gpio.015 (I/O 15?) |
| 6 | Eixo Y | gpio.030? |
| 7 | Eixo Z | gpio.031? |
| 8 | Reservado | - |
| 9 | Escala x100 | a confirmar |
| 10 | E-Stop contato | - |
| 11 | Eixo X | gpio.026? |
| 12 | Eixo 5 | - |
| 13 | Reservado | - |
| 14 | COM (GND) | 0V |
| 15 | +5V | +5V |

NOTA: O mapeamento DB15 pino -> GPIO precisa ser confirmado com teste.
Os GPIOs do HAL de referencia (015, 016, 026, 030, 031) podem nao corresponder
ao firmware atual. Usar o readhmid + teste fisico pra confirmar.

### 2.4 Dump de GPIOs (com LinuxCNC rodando)

```
gpio.000.in = FALSE    gpio.017.in = TRUE  ← ENCODER A (travado!)
gpio.001.in = FALSE    gpio.018.in = TRUE  ← ENCODER B (travado!)
gpio.002.in = FALSE    gpio.019.in = TRUE  (E-stop)
gpio.003.in = FALSE    gpio.020.in = TRUE
gpio.004.in = FALSE    gpio.021.in = TRUE
gpio.005.in = FALSE    gpio.022.in = TRUE
gpio.006.in = FALSE    gpio.023.in = TRUE
gpio.007.in = FALSE    gpio.024.in = TRUE
gpio.008.in = FALSE    gpio.025.in = FALSE
gpio.009.in = FALSE    gpio.026.in = TRUE
gpio.010.in = FALSE    gpio.027.in = TRUE
gpio.011.in = FALSE    gpio.028.in = FALSE
gpio.012.in = FALSE    gpio.029.in = FALSE
gpio.013.in = FALSE    gpio.030.in = TRUE
gpio.014.in = TRUE     gpio.031.in = TRUE
gpio.015.in = TRUE     gpio.032.in = FALSE
gpio.016.in = TRUE     gpio.033.in = FALSE
```

### 2.5 AMS32ES2 - PLC Industrial (para painel, FASE 3)

- PLC 24V, 16DI (X0-X17), 16DO (Y0-Y17)
- 4 entradas encoder AB phase
- 2x RS-485 (Modbus RTU para LinuxCNC via mb2hal)
- SEM entradas analogicas
- Integracao futura via USB-RS485 no PC

### 2.6 Hardware descartado

BIGTREETECH Octopus, Mini 12864, FYSETC Display = impressora 3D, incompativeis.

---

## 3. Problema Encoder Spindle - DIAGNOSTICADO

### Sintomas (confirmados 2026-04-06)
- encoder.00.input-a = TRUE (fixo, nao muda ao girar)
- encoder.00.input-b = TRUE (fixo, nao muda ao girar)
- encoder.00.input-index = TRUE (fixo)
- encoder.00.rawcounts = 0
- NENHUM GPIO (000-033) mudou ao girar o spindle

### Causa CONFIRMADA
O borne fisico de encoder na placa (rotulado "1路输入") **NAO esta conectado
a NENHUM pino do FPGA**. E um conector morto nesta placa chinesa.
GPIO 017/018 (onde encoder.00 mapeia A/B) tem pull-up interno e ficam TRUE.
Diagnostico feito com `diag_encoder2.sh` em 2026-04-06.

### Dump completo dos GPIOs (2026-04-06)
```
P2 (I/O 00-16): gpio.000-012 = FALSE, gpio.013 = saida (spindle CW)
                gpio.014-016 = TRUE (pull-up, entradas livres)

P1 (I/O 17-33): gpio.017-024 = TRUE (pull-up)
                gpio.025 = FALSE  ← LIVRE
                gpio.026 = TRUE (pull-up, reservado MPG eixo X)
                gpio.027 = TRUE (pull-up)
                gpio.028 = FALSE  ← LIVRE
                gpio.029 = FALSE  ← LIVRE
                gpio.030 = TRUE (reservado MPG eixo Y)
                gpio.031 = TRUE (reservado MPG eixo Z)
                gpio.032 = FALSE  ← LIVRE
                gpio.033 = FALSE  ← LIVRE
```

### Solucao DEFINITIVA: RELIGAR ENCODER NOS PINOS 3,4 DO DB15

O conector DB15 (P1) tem pinos que mapeiam direto para I/O 17 e 18 do FPGA,
onde o firmware coloca o modulo encoder.00 (QCount canal 0).
Basta religar o encoder do spindle nesses pinos e o **HAL funciona sem
nenhuma alteracao** - encoder.00 hardware le direto.

**Religacao fisica (4 fios):**
```
Encoder spindle          DB15 (P1) na placa
  Fio A ──────────────── Pino 4 do DB15 (I/O 17 = encoder.00.A)
  Fio B ──────────────── Pino 3 do DB15 (I/O 18 = encoder.00.B)
  +5V ────────────────── Pino 15 do DB15 (+5V)
  GND ────────────────── Pino 14 do DB15 (COM/GND)
```

**Por que funciona:**
- readhmid mostra: I/O 17 = QCount 0 Quad-A, I/O 18 = QCount 0 Quad-B
- Pinagem DB15 (手轮针脚定义.png): pino 4 = Encoder A, pino 3 = Encoder B
- HAL ja tem encoder.00 configurado com scale=400, filtro, at-speed
- **Zero alteracoes em Dino_Evo.hal, custom.hal ou Dino_Evo.ini**

**RESOLVIDO em 2026-04-06:** Encoder religado no DB15, encoder.00 hardware
funcionando. rawcounts muda ao girar, velocity/RPM lendo corretamente.

**Sobre Index (Z) para rosqueamento:**
O firmware NAO tem pin de index no encoder. Opcoes futuras:
a) Flashear firmware diferente que inclua index
b) Ligar fio Index do encoder num GPIO e usar software encoder com index
c) Usar counter-mode=1 (sem index, conta pulsos de A apenas)

---

## 4. Configuracao LinuxCNC Atual (funcionando)

### 4.1 Dino_Evo.ini - Destaques

```ini
[DISPLAY]
DISPLAY = probe_basic_lathe
BACK_TOOL_LATHE = 1
MAX_SPINDLE_OVERRIDE = 2.000000   # alterado de 1.0
MAX_FEED_OVERRIDE = 2.000000
LATHE = 1

[HAL]
HALFILE = Dino_Evo.hal
HALFILE = custom.hal              # adicionado
HALUI = halui
POSTGUI_HALFILE = probe_basic_postgui_fix.hal

[TRAJ]
SPINDLES = 1
COORDINATES = X Z

[KINS]
KINEMATICS = trivkins coordinates=xz
JOINTS = 2

[JOINT_0]  # Eixo X
STEP_SCALE = -500.0
MAX_VELOCITY = 75.0
MAX_ACCELERATION = 2250.0

[JOINT_1]  # Eixo Z
STEP_SCALE = -500.0
MAX_VELOCITY = 72.0
MAX_ACCELERATION = 1350.0

[SPINDLE_0]
FF0 = 1  (P=0, I=0, D=0 - passthrough)
MAX_OUTPUT = 2000
ENCODER_SCALE = 400
```

### 4.2 Dino_Evo.hal - Estrutura

```
Carregamento: hostmot2, hm2_eth (num_enc=1, num_pwm=3, num_step=5)
              pid (x, z, s), near.spindle, abs.spindle, lowpass.spindle, scale.spindle

Eixo X:      pid.x -> stepgen.00 (closed-loop stepper)
Eixo Z:      pid.z -> stepgen.01 (closed-loop stepper)
Spindle:     pid.s -> pwmgen.00 (scale 2000, output-type 1)
             gpio.013 = spindle CW (saida)
             encoder.00 (scale=[SPINDLE_0]ENCODER_SCALE)
             near.spindle (at-speed, scale 1.5)
             Filtro: scale(x60) -> abs -> lowpass -> display RPM
Coolant:     pwmgen.01 (50% duty)
E-Stop:      gpio.019 (entrada NF)
Tool change: hal_manualtoolchange
Feed ovr:    setp preparados (sem fonte, aguardando mb2hal)
```

### 4.3 custom.hal - Estado atual

MPG DESABILITADO. Firmware so tem 1 encoder.
Arquivo contem apenas comentarios explicando as opcoes A (novo firmware) e B (software encoder via GPIO).

### 4.4 probe_basic_postgui_fix.hal

- Timer de ciclo (time component -> qtpyvcp.timer*)
- RPM display (spindle-fb-rpm-abs-filtered -> qtpyvcp.spindle-encoder-rpm.in)
- Tool change conectado ao qtpyvcp_manualtoolchange

---

## 5. Arquitetura Planejada do Painel

```
MESA 7i92 (tempo real)          AMS32ES2 (Modbus, ~20-50ms)
├── Eixo X - stepgen.00         ├── Feed Override (encoder AB)
├── Eixo Z - stepgen.01         ├── Spindle Override (encoder AB)
├── Spindle encoder             ├── Botoes painel (X0-X17)
├── Spindle PWM - pwmgen.00     └── LEDs painel (Y0-Y17)
├── Spindle CW - gpio.013
├── Coolant - pwmgen.01
├── E-Stop - gpio.019
└── MPG Handwheel (DB15) ← bloqueado: precisa resolver encoder
```

### Mapa I/O AMS32ES2 (planejado)

**Entradas:** X0=CycleStart, X1=FeedHold, X2=SpindleCW, X3=SpindleCCW,
X4=SpindleStop, X5=Coolant, X6=HomeX, X7=HomeZ, X10-X13=Tool T1-T4,
X14=Manual/Auto, X15-X17=spare

**Saidas:** Y0=MachineON, Y1=XHomed, Y2=ZHomed, Y3=SpindleCW,
Y4=SpindleCCW, Y5=Coolant, Y6=Running, Y7=Erro, Y10-Y17=spare

**Encoders AB:** 1=FeedOvr, 2=SpindleOvr, 3-4=spare

---

## 6. Arquivos do Projeto

### G:\CyberDino\Linuxcnc\ (copiar para /home/evo/linuxcnc/configs/Dino_Evo/)
- `Dino_Evo.ini` - INI principal (ALTERADO)
- `Dino_Evo.hal` - HAL principal (ALTERADO)
- `custom.hal` - MPG desabilitado (ALTERADO)
- `probe_basic_postgui_fix.hal` - Timer + RPM display
- `custom_config.yml` - Config QtPyVCP
- `custom_postgui.hal`, `custom_gvcp.hal`, `shutdown.hal` - vazios
- `probe_basic_lathe.ini` - referencia simulador
- `probe_basic_evo.qss` - stylesheet
- `tool.tbl`, `linuxcnc.var` - tabelas
- `subroutines/` - G-code (probe, touch-off, threading, etc)
- `hallib/` - HAL simulacao
- `user_buttons/`, `user_dro_display/`, `user_tabs/` - UI customizada
- `python/` - remap.py, stdglue.py, toplevel.py

### G:\CyberDino\Arquivos mes\ (referencia, NAO copiar para maquina)
- `7i92_5ABOB_Enc.bit` - firmware atual
- `4轴固件多了2个PWM输出.bit` - firmware alternativo
- `mesa（部分配置可参考）.hal` - HAL referencia chinesa
- `7i92命令.txt` - comandos mesaflash
- `引脚定义.jpg` - layout da placa
- `手轮针脚定义.png` - pinagem DB15
- `7i92一体板V1.0引脚分配表格.xls` - tabela completa de pinos

### G:\CyberDino\FIACAO_MPG_PAINEL.html
Documento de fiacao para impressao (PDF via navegador Ctrl+P).
Contem diagrama DB15, encoder, E-stop, spindle, coolant.

---

## 7. Decisoes e Restricoes

| Item | Decisao/Restricao |
|------|-------------------|
| Probe | NAO usar (decisao do usuario) |
| Firmware | So suporta 1 encoder, sem Index Z |
| num_encoders | Maximo 1 (tentou 2, falhou) |
| MPG | Desabilitado ate resolver encoder ou flashear firmware |
| Mesa = tempo real | Eixos, spindle, encoder, E-stop, coolant |
| PLC = painel | Botoes, LEDs, override (via Modbus mb2hal) |
| Override | Por encoder rotativo (PLC tem AB phase, sem analogico) |
| ProbeBasic | Manter (ja funciona) |

---

## 8. Comandos Uteis

```bash
# Mesa - info
sudo mesaflash --device 7i92 --addr 10.10.10.10 --readhmid
sudo mesaflash --device 7i92 --addr 10.10.10.10 --verbose

# Mesa - flashear firmware (FECHAR LINUXCNC ANTES)
sudo mesaflash --device 7i92 --addr 10.10.10.10 --write FIRMWARE.bit --fix --fallback
sudo mesaflash --device 7i92 --addr 10.10.10.10 --write FIRMWARE.bit --fallback
sudo mesaflash --device 7i92 --addr 10.10.10.10 --reload --fallback
sudo mesaflash --device 7i92 --addr 10.10.10.10 --write FIRMWARE.bit --fix
sudo mesaflash --device 7i92 --addr 10.10.10.10 --write FIRMWARE.bit
sudo mesaflash --device 7i92 --addr 10.10.10.10 --reload

# HAL debug (com LinuxCNC aberto)
halcmd show pin hm2_7i92.0.encoder
halcmd show pin hm2_7i92.0.gpio
halcmd show sig spindle-at-speed
halcmd show sig spindle-fb-rpm-abs-filtered
halcmd getp hm2_7i92.0.encoder.00.rawcounts

# Rede
ping 10.10.10.10
# PC precisa IP 10.10.10.1 /8 (sem gateway)
```

---

## 9. Proximo Passo Imediato

**RESOLVER ENCODER SPINDLE** - O encoder esta fisicamente ligado no borne
da placa mas os sinais nao chegam nos pinos I/O 17 e 18 do FPGA (onde o
firmware colocou o modulo encoder.00).

Teste a fazer:
```bash
halcmd show pin hm2_7i92.0.gpio | grep "\.in " > /tmp/parado.txt
# GIRAR SPINDLE
halcmd show pin hm2_7i92.0.gpio | grep "\.in " > /tmp/girando.txt
diff /tmp/parado.txt /tmp/girando.txt
```

O diff revela em quais GPIOs o encoder realmente chega.
Depois: usar software encoder nesses GPIOs ou religar fios nos pinos corretos.
