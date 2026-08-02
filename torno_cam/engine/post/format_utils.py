"""Port de packages/postprocessor/src/formatUtils.ts."""

import re

from ..jsutil import js_tofixed

_TRAIL = re.compile(r"\.?0+$")


def fmt(n, decimals=3):
    """Formata numero com N casas, removendo zeros a direita. None -> ''."""
    if n is None:
        return ""
    return _TRAIL.sub("", js_tofixed(n, decimals)) or "0"


def fmt_fixed(n, decimals=3):
    """Formata mantendo zeros a direita. None -> ''."""
    if n is None:
        return ""
    return js_tofixed(n, decimals)


def word(letter, value, decimals=3):
    """Monta uma palavra G-code so se value estiver definido (None -> '')."""
    if value is None:
        return ""
    return "{}{}".format(letter, fmt(value, decimals))


def gline(*words):
    """Junta palavras nao-vazias com espaco."""
    return " ".join(w for w in words if w)
