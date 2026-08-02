# torno_cam — gerador conversational de torno (port do EvoCAM)

Engine Python puro que gera G-code de torno a partir de parametros de
operacao (facear, desbaste, furar, rosca...). Portado do app TS EvoCAM
(`../Evo-CNC-Guia`), com **paridade byte-a-byte** verificada contra o engine
original.

## Estrutura

```
torno_cam/                 # ENGINE PURO (sem Qt / LinuxCNC) — importavel por testes
  engine/
    jsutil.py              # semantica numerica do JS (Math.round, toFixed, ${})
    nodes.py               # IR ToolpathNode + ToolpathBuilder
    sfm.py                 # RPM/CSS (SFMCalculator)
    threading_engine.py    # matematica de rosca
    strategies/            # face, drill, od_turn, thread + build_nodes()
    post/
      format_utils.py      # fmt/word/gline
      base.py              # PostProcessor (template method)
      linuxcnc.py          # porte FIEL (alvo de paridade; inclui emissoes invalidas)
      linuxcnc_dino.py     # dialeto da maquina (G33, ASCII, ciclos fixos bloqueados)
    program.py             # entry_from_nodes + assemble_program
    defaults.py            # defaults metricos por operacao (p/ a UI)
  tests/                   # pytest: paridade (golden) + comportamento

../torno_cam_ui/           # UI Qt (aba GERAR PGM) — depende de qtpy/qtpyvcp
../user_tabs/gerar_pgm/    # shim que o ProbeBasic carrega (reexporta UserTab)
```

O engine e o dialeto correto (`LinuxCNCDinoPost`) sao o que a UI usa. O porte
fiel (`LinuxCNCPost`) existe **so** para travar a paridade — ele reproduz ate
os bugs do TS (G32 em vez de G33, G75/G71 invalidos, G81 sob G18). Nunca use
o porte fiel na maquina.

## Rodar os testes

```bash
cd /home/evo/linuxcnc/configs/Dino_Evo
python3 -m pytest torno_cam/tests -q
```

## Regerar os goldens (quando o engine TS mudar)

```bash
cd /home/evo/linuxcnc/configs/Dino_Evo/Evo-CNC-Guia
GOLDEN_DIR=/home/evo/linuxcnc/configs/Dino_Evo/torno_cam/tests/golden \
  pnpm --filter @cnc-studio/postprocessor exec vitest run src/golden/golden.spec.ts
```

Matriz de casos: `Evo-CNC-Guia/packages/postprocessor/src/golden/golden.spec.ts`.

## Estado (2026-07-30)

- **Fase 0** (engine + paridade): pronta. 88 testes verdes.
- **Fase 1** (aba MVP: FACEAR, DESBASTE EXT, FURAR, ROSCA): pronta, testada
  headless (offscreen). Falta validar na maquina/sim.
- **Fase 2** (chanfro, canal, desbaste interno): pendente.
- **Fase 3** (ciclos fixos G71/G76 corrigidos): pendente — hoje bloqueados na
  UI (so modo manual linha-a-linha, que e valido no LinuxCNC 2.9.7).

Plano completo: `.claude/plans/dynamic-painting-cat.md`.
```
