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

# Escreve direto, com o LinuxCNC no ar ou nao: o salva_posicao.py OBEDECE o
# arquivo de estado e rele ele antes de cada gravacao, inclusive na de saida.
for n in 0 1; do
    cp "home_chave_joint${n}.inc" "home_joint${n}.inc"
done
echo chave > modo_referenciamento.txt
echo botao > chave_armada.marca
echo "Referenciamento na chave armado para o proximo boot."

if [ "$1" = "--iniciar" ]; then
    exec linuxcnc Dino_Evo.ini
fi
echo "Inicie o LinuxCNC normalmente (ou rode com --iniciar)."
