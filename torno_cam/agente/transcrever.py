# -*- coding: utf-8 -*-
"""Transcricao de voz do chat do agente (Whisper local, sem internet).

Roda no ambiente separado do Whisper (~/.local/share/agente_torno/voz), nao
no Python do LinuxCNC: o faster-whisper traz numpy e bibliotecas proprias que
nao podem misturar com as do qtpyvcp/VTK.

Modo servidor (o que a aba usa): fica aberto com o modelo carregado; cada
linha no stdin e' o caminho de um .wav e cada resposta e' uma linha JSON
{"texto": ..., "erro": ...} no stdout. A primeira linha e' {"pronto": true}.

    python transcrever.py --servidor
    python transcrever.py arquivo.wav        (uma vez, para teste)
"""

import json
import os
import sys

MODELO = os.environ.get("AGENTE_VOZ_MODELO", "small")
PASTA_MODELOS = os.path.expanduser(
    os.environ.get("AGENTE_VOZ_MODELOS", "~/.local/share/agente_torno/voz/modelos"))

# Dica de ESTILO (como escrever as medidas), sem exemplos de pedido: testado
# com frases faladas, uma dica com comandos inteiros ("facear Ø50 de Z3...",
# "aço 1045") fazia o Whisper copiar pedacos dela para o texto, trocando
# valores ditos por valores da dica. Uma lista de palavras (hotwords) tambem
# vazava para o texto.
DICA = u"Pedido para o torno CNC, com as medidas escritas em números: Ø50, Z-40, 0,5 mm."


def carregar():
    from faster_whisper import WhisperModel
    return WhisperModel(MODELO, device="cpu", compute_type="int8",
                        download_root=PASTA_MODELOS)


def transcrever(modelo, wav):
    segmentos, _info = modelo.transcribe(
        wav, language="pt", initial_prompt=DICA, beam_size=5,
        vad_filter=True, condition_on_previous_text=False)
    return " ".join(s.text.strip() for s in segmentos).strip()


def servidor():
    try:
        modelo = carregar()
    except Exception as e:                       # sem faster-whisper ou sem modelo
        print(json.dumps({"pronto": False, "erro": str(e)}), flush=True)
        return
    print(json.dumps({"pronto": True}), flush=True)
    for linha in sys.stdin:
        wav = linha.strip()
        if not wav:
            continue
        try:
            resp = {"texto": transcrever(modelo, wav), "erro": None}
        except Exception as e:
            resp = {"texto": "", "erro": str(e)}
        print(json.dumps(resp, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--servidor":
        servidor()
    elif len(sys.argv) > 1:
        print(transcrever(carregar(), sys.argv[1]))
    else:
        print(__doc__)
