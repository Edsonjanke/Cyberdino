# -*- coding: utf-8 -*-
"""Aba GERAR PGM (shim). O ProbeBasic carrega ESTE arquivo via
spec_from_file_location (modulo standalone, sem pacote pai), entao imports
relativos nao funcionam aqui. A implementacao real mora no pacote importavel
`torno_cam_ui` na raiz do config; aqui so garantimos a raiz no sys.path e
reexportamos UserTab."""

import os
import sys

_CONFIG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _CONFIG_ROOT not in sys.path:
    sys.path.insert(0, _CONFIG_ROOT)

from torno_cam_ui.tab import UserTab   # noqa: E402  (reexport p/ o loader)

__all__ = ["UserTab"]
