# Caixa de Marchas e Aba CUSTOMS

Implementado em 2026-04-29.

## Resumo

O torno tem caixa de marchas mecanica de 2 posicoes (troca manual com maquina parada):
- **Marcha ALTA**: max 2360 RPM no chuck, ratio 1:1 motor/chuck
- **Marcha REDUZIDA**: max 600 RPM no chuck, ratio 1:3.9333 (2360/600)

Selecao via botao toggle na **aba CUSTOMS** da interface ProbeBasic.
Estado persiste entre sessoes via `QSettings(DinoEvo/Gearbox)`.
Botao desabilitado quando spindle gira (M3/M4 ativo).

## Arquitetura HAL

Cadeia em [[11 - HAL Spindle VFD 9600|Dino_Evo.hal]]:

```
spindle.0.speed-out (chuck RPM, signed)
   |
   |--> limit2.spindle-cmd-high (clampa +/-2360)
   |--> limit2.spindle-cmd-low  (clampa +/-600)
                |
                v
        mux2.spindle-cmd (sel = gear-low)
                |
                v
        cmd-clamped --> pid.s.command
                              |
                              v
                        pid.s.output (chuck RPM clampado)
                              |
                              v
                  mult2.spindle-gear  (in1 = ratio 1.0 ou 3.9333)
                              |
                              v
                       motor RPM equivalente
                              |
                              v
                  scale.spindle-pwm  (linearizacao VFD: 1.727*x - 88.6)
                              |
                              v
                      pwmgen.00.value (scale 4980)
```

## Componentes adicionados

```hal
loadrt mult2  names=mult2.spindle-gear
loadrt mux2   names=mux2.spindle-cmd,mux2.gear-factor
loadrt limit2 names=limit2.spindle-cmd-high,limit2.spindle-cmd-low

setp limit2.spindle-cmd-high.max  2360
setp limit2.spindle-cmd-high.min -2360
setp limit2.spindle-cmd-high.maxv 1e9
setp limit2.spindle-cmd-low.max   600
setp limit2.spindle-cmd-low.min  -600
setp limit2.spindle-cmd-low.maxv  1e9

setp mux2.gear-factor.in0  1.0
setp mux2.gear-factor.in1  3.9333
```

## Sinal gear-low

- **Source**: `qtpyvcp.gear-button.checked` (TRUE = reduzida) — vem do GearButton da aba CUSTOMS
- **Destinos**:
  - `mux2.spindle-cmd.sel` (seleciona qual limit2 alimenta o PID)
  - `mux2.gear-factor.sel` (seleciona ratio que multiplica saida do PID)

Wired no `probe_basic_postgui_fix.hal`:
```hal
net gear-low <= qtpyvcp.gear-button.checked
net spindle-enable => qtpyvcp.gear-button.spinning
```

## Encoder na placa (chuck)

Como o encoder esta direto na arvore (nao no motor), a leitura de RPM e os pulsos por revolucao sao do **chuck real**, em qualquer marcha. Isso garante:
- `at-speed` compara cmd_chuck vs fb_chuck corretamente
- Threading G33/G76 funciona em ambas as marchas (pulsos por rev sao do chuck)
- PID controla velocidade do chuck diretamente

## Comportamento se exceder a marcha

Se usuario comandar S>max-da-marcha:
- limit2 clampa o cmd no maximo da marcha
- PID atinge cmd_chuck=max, motor saturado
- `near.spindle` (at-speed) compara cmd-rps-abs (sinal NAO clampado, vem direto de spindle.0.speed-out-rps-abs) vs feedback
- at-speed fica FALSE eternamente -> seguranca natural, operador percebe que excedeu

## Aba CUSTOMS

Nova user_tab em `user_tabs/customs/`:
- `customs.py` — classe UserTab que carrega o .ui
- `customs.ui` — layout com 2 group boxes:
  - **CAIXA DE MARCHAS**: GearButton grande (toggle ALTA 2360 / REDUZIDA 600)
  - **CONTADOR DE PECAS**: HalLabel com display do `partcounter.count` + HalButton RESET

Habilitada via `[DISPLAY] USER_TABS_PATH = user_tabs/` no INI.

## GearButton custom widget

Em `mpg_button.py` (instalado em `~/.local/lib/python3.11/site-packages/`):

```python
class GearButton(QPushButton, HALWidget, VCPWidget):
    """HAL pins:
      .checked  (bit out)  - estado da marcha (TRUE = reduzida)
      .spinning (bit in)   - desabilita botao quando spindle ligado
    Estado salvo em QSettings(DinoEvo/Gearbox).
    """
```

Visual: muda label e cor (alta=cinza / reduzida=laranja). Desabilita (cinza escuro) quando `qtpyvcp.gear-button.spinning` = TRUE.

## Contador de pecas

O `partcounter.py` (loadusr) era exibido antes via codigo Python no `dros_xz.py` (com QTimer + subprocess halcmd). Migrou para a aba CUSTOMS:
- Display via `HalLabel` ligado em `qtpyvcp.parts-count.in <= partcounter.count`
- Reset via `HalButton` (pulse 200ms) ligado em `qtpyvcp.parts-reset.out => partcounter.reset`

## Calibracao da marcha reduzida

Se a relacao real for diferente de 3.9333:
1. Em marcha reduzida, comande M3 S<algum_valor>
2. `halcmd getp hm2_7i92.0.encoder.01.velocity-rpm` -> ler RPM real do chuck
3. Se RPM real != cmd, ajustar:
   - `setp mux2.gear-factor.in1 <novo_ratio>`
   - novo_ratio = ratio_atual * (cmd / rpm_real)
4. Persistir em `Dino_Evo.hal` editando o `setp` na secao CAIXA DE MARCHAS.

## Velocidades dos eixos (mesma sessao, 2026-04-29)

- **X**: 75.0 -> **86.25 mm/s** (+15%) — STEPGEN_MAXVEL 93.75 -> 107.8125
- **Z**: 72.0 -> **93.6 mm/s** (+30%) — STEPGEN_MAXVEL 90.0 -> 117.0
- **TRAJ MAX_LINEAR_VELOCITY**: 135.00 -> **202.50 mm/s** (+50%)

Aceleracoes nao alteradas.

## Programa de furo (G18 -> G17)

Programas vindo de torno Fanuc/Mazak usam `G18 G83` para furar em Z. No LinuxCNC G18 fura em Y (eixo inexistente neste torno) -> erro "Ciclo G18 nao possivel em maquina sem eixo Y".

**Solucao**: trocar `G18` por `G17` antes do G83 (a sub `subroutines/drill.ngc` ja usa esse padrao).

---

**Ver tambem:**
- [[11 - HAL Spindle VFD 9600]] — cadeia completa do PWM
- [[12 - ProbeBasic Interface Custom]] — outras customizacoes da UI
- [[20 - Parametros VFD 9600]] — codigos de aceleracao/desaceleracao do inversor
