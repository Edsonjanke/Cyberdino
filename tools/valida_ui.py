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
from qtpy.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
                            QLineEdit, QDoubleSpinBox)
app = QApplication([])
class _ModuloFalso(types.ModuleType):
    """Devolve um widget simples para QUALQUER classe pedida.

    Assim o validador serve pra qualquer .ui do projeto sem precisar listar
    os widgets um a um — foi o que fez ele falhar com o customs.ui, que usa
    JogIncrement, GearSelector e companhia."""

    BASES = {
        "button": QPushButton, "btn": QPushButton, "selector": QPushButton,
        "spin": QDoubleSpinBox,          # tem setMinimum/setMaximum
        "edit": QLineEdit, "entry": QLineEdit,
    }

    def __getattr__(self, nome):
        base = QLabel
        for marca, classe in self.BASES.items():
            if marca in nome.lower():
                base = classe
                break
        tipo = type(nome, (base,), {})
        # enums que alguns .ui usam em propriedades (ex.: HalLabel.s32)
        for i, enum in enumerate(("bit", "s32", "u32", "float")):
            setattr(tipo, enum, i)
        setattr(self, nome, tipo)
        return tipo


for _mod in ("qtpyvcp.widgets.display_widgets.status_label",
             "qtpyvcp.widgets.display_widgets.dro_label",
             "qtpyvcp.widgets.input_widgets.dro_line_edit",
             "qtpyvcp.widgets.hal_widgets.hal_label",
             "qtpyvcp.widgets.hal_widgets.hal_button",
             "qtpyvcp.widgets.hal_widgets.hal_spinbox",
             "qtpyvcp.widgets.button_widgets.mdi_button",
             "qtpyvcp.widgets.button_widgets.action_button",
             "qtpyvcp.widgets.input_widgets.jog_increment",
             "mpg_button"):
    sys.modules[_mod] = _ModuloFalso(_mod)

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
