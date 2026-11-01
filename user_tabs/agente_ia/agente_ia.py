# -*- coding: utf-8 -*-
"""Aba AGENTE IA (shim). O ProbeBasic carrega ESTE arquivo via
spec_from_file_location (modulo standalone), entao a implementacao mora no
pacote `torno_cam_ui` da raiz do config, como na aba GERAR PGM."""

import os
import sys

_CONFIG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _CONFIG_ROOT not in sys.path:
    sys.path.insert(0, _CONFIG_ROOT)

from torno_cam_ui.agente_tab import UserTab   # noqa: E402  (reexport p/ o loader)

__all__ = ["UserTab"]
