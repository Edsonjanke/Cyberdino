#!/bin/bash
# Sobe o SIM (Dino_Evo_sim.ini) numa tela virtual, pra testar interface sem
# a maquina.
#
#     tools/roda_sim.sh [segundos]
#
# RECUSA RODAR COM O LINUXCNC DE VERDADE ABERTO. O sim precisa do realtime
# livre, e o `halrun -U` que isso exige DERRUBA a HAL da sessao em
# andamento — as janelas ficam na tela e nao ha mais HAL por tras.
# Aconteceu duas vezes em 2026-10-16, a segunda com a maquina ligada.
# (A posicao foi salva certo nas duas, pelo salva_posicao.py, que trata o
# SIGTERM — mas isso e' sorte, nao projeto.)
set -u
SEGUNDOS="${1:-150}"
AQUI="$(cd "$(dirname "$0")/.." && pwd)"
cd "$AQUI" || exit 1

if pgrep -x linuxcncsvr >/dev/null 2>&1; then
    echo "RECUSADO: o LinuxCNC esta aberto."
    echo "Feche-o antes — subir o sim derrubaria a HAL da sessao que esta"
    echo "rodando, e a maquina ficaria sem controle por tras da tela."
    exit 2
fi

halrun -U >/dev/null 2>&1
timeout "$SEGUNDOS" xvfb-run -a -s "-screen 0 1920x1080x24" \
    linuxcnc Dino_Evo_sim.ini
CODIGO=$?
halrun -U >/dev/null 2>&1
exit $CODIGO
