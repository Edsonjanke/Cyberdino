#!/bin/bash
# CyberDino - Volta o referenciamento para a CHAVE (GPIO.014) na proxima
# vez que o LinuxCNC subir.
#
# O uso normal e' ligar com a posicao salva (o LinuxCNC adota onde o eixo
# ficou, sem mover). Rode este script quando a posicao salva nao valer mais:
# alguem girou o eixo com a maquina desligada, bateu, o servo alarmou, ou o
# LinuxCNC morreu de um jeito feio.
#
# Depois do referenciamento na chave, o salva_posicao.py volta a gravar a
# posicao sozinho — nao precisa desfazer nada.
set -e
cd "$(dirname "$0")"

if pgrep -x linuxcncsvr >/dev/null; then
    # LinuxCNC no ar: quem escreve nos .inc e' o salva_posicao.py. Sem isso
    # o encerramento regravaria a posicao por cima e desarmaria a chave.
    touch armar_chave.flag
    sleep 1
else
    for n in 0 1; do
        cp "home_chave_joint${n}.inc" "home_joint${n}.inc"
    done
fi
echo "Referenciamento na chave armado para o proximo boot."

if [ "$1" = "--iniciar" ]; then
    exec linuxcnc Dino_Evo.ini
fi
echo "Inicie o LinuxCNC normalmente (ou rode com --iniciar)."
