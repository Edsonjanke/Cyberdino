#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Valida um .ui com o MESMO carregador que o LinuxCNC usa (uic.loadUi),
trocando os widgets do qtpyvcp por equivalentes simples.

Por que existe: o `pyuic` compila o arquivo sem reclamar de propriedades que
o carregador em tempo de execucao NAO aceita, e o estrago aparece so na
maquina — pela metade. Foi o caso do `stretch` num QHBoxLayout: o pyuic
ignorava e o uic estourava com

    TypeError: setStretch(self, index: int, stretch: int):
               argument 1 has unexpected type 'str'

deixando o DRO montado ate aquele ponto e o resto sem existir. Para dividir
um layout em partes iguais, use horstretch no sizePolicy de cada widget.

USO
---
    QT_QPA_PLATFORM=offscreen python3 tools/valida_ui.py <arquivo.ui> [prefixo]

O prefixo e' opcional e lista os widgets criados que comecam com ele — serve
pra conferir que a parte que voce mexeu realmente entrou.

Nao serve para o probe_basic_custom.ui inteiro: ele puxa widgets do
ProbeBasic que exigem o LinuxCNC rodando."""
import sys, types
from qtpy.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QLineEdit
app = QApplication([])
def stub(mod, **classes):
    m = types.ModuleType(mod)
    for k, base in classes.items():
        setattr(m, k, type(k, (base,), {}))
    sys.modules[mod] = m
stub("qtpyvcp.widgets.display_widgets.status_label", StatusLabel=QLabel)
stub("qtpyvcp.widgets.display_widgets.dro_label", DROLabel=QLabel)
stub("qtpyvcp.widgets.input_widgets.dro_line_edit", DROLineEdit=QLineEdit)
stub("qtpyvcp.widgets.hal_widgets.hal_label", HalLabel=QLabel)
# o .ui usa enums do HalLabel (pinType); o stub precisa te-los
_hl = sys.modules["qtpyvcp.widgets.hal_widgets.hal_label"].HalLabel
for _i, _n in enumerate(("bit", "s32", "u32", "float")):
    setattr(_hl, _n, _i)
stub("qtpyvcp.widgets.button_widgets.mdi_button", MDIButton=QPushButton)
stub("qtpyvcp.widgets.button_widgets.action_button", ActionButton=QPushButton)
stub("mpg_button", GearLabel=QLabel, GearSelector=QPushButton, MPGButton=QPushButton)
from qtpy import uic
alvo, prefixo = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
w = QWidget()
try:
    uic.loadUi(alvo, w)
except Exception as e:
    print("FALHOU: %s: %s" % (type(e).__name__, e)); sys.exit(1)
nomes = [c.objectName() for c in w.findChildren(QWidget)
         if prefixo and c.objectName().startswith(prefixo)]
print("OK — %d widgets" % len(w.findChildren(QWidget)), ("| %s: %s" % (prefixo, nomes)) if prefixo else "")
