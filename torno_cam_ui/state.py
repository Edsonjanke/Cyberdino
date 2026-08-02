# -*- coding: utf-8 -*-
"""Persistencia dos params da UI + utilidades de arquivo (.ngc)."""

import json
import os
import re
import unicodedata


def config_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)   # torno_cam_ui -> raiz do config


def program_prefix():
    """Diretorio nc_files (PROGRAM_PREFIX do INI); fallback ~/linuxcnc/nc_files."""
    try:
        import linuxcnc
        ini = linuxcnc.ini(os.getenv("INI_FILE_NAME"))
        p = ini.find("DISPLAY", "PROGRAM_PREFIX")
        if p:
            return os.path.expanduser(p)
    except Exception:
        pass
    return os.path.expanduser("~/linuxcnc/nc_files")


def sanitize_filename(title):
    s = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_")
    return s or "programa"


def unique_path(directory, base, ext=".ngc"):
    """Caminho que nao sobrescreve: base.ngc, base-1.ngc, base-2.ngc ..."""
    path = os.path.join(directory, base + ext)
    n = 1
    while os.path.exists(path):
        path = os.path.join(directory, "{}-{}{}".format(base, n, ext))
        n += 1
    return path


# TORNO_CAM_STATE redireciona o arquivo de estado (testes usam um descartavel
# para nao sobrescrever os valores que o operador deixou salvos na maquina).
_STATE_PATH = os.getenv("TORNO_CAM_STATE") or \
    os.path.join(config_root(), "torno_cam_ui.json")


def load_state():
    try:
        with open(_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(data):
    try:
        with open(_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
