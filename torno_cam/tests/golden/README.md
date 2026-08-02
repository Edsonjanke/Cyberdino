# Goldens de paridade (gerados pelo engine TS)

Cada caso tem dois arquivos:
- `<id>.params.json` — `{config, ops:[{label, params}]}` (entrada exata)
- `<id>.ngc` — G-code que o engine TS (LinuxCNCPost fiel) produz

O `test_golden_parity.py` remonta cada caso com o engine Python e compara
string-a-string. **Não edite os .ngc à mão** — regere pelo TS.

## Regerar

```bash
cd /home/evo/linuxcnc/configs/Dino_Evo/Evo-CNC-Guia
GOLDEN_DIR=/home/evo/linuxcnc/configs/Dino_Evo/torno_cam/tests/golden \
  pnpm --filter @cnc-studio/postprocessor exec vitest run src/golden/golden.spec.ts
```

A matriz de casos está em
`Evo-CNC-Guia/packages/postprocessor/src/golden/golden.spec.ts`.
Para adicionar um caso, edite a matriz lá e regere.

## Rodar a paridade (Python)

```bash
cd /home/evo/linuxcnc/configs/Dino_Evo
python3 -m pytest torno_cam/tests -q
```
