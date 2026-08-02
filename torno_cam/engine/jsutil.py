"""Reproducao EXATA da semantica numerica do JavaScript, para paridade
byte-a-byte com o engine TS original.

Tres regras que divergem do Python "ingenuo":
- Math.round(x)      = floor(x + 0.5)  (assimetrico p/ negativos; -2.5 -> -2)
- Number.toFixed(nd) = escolhe o inteiro n que minimiza |n/10^nd - x|; no
  empate escolhe o MAIOR n (viés +infinito). Reproduzido com Decimal exato.
- `${num}` (template literal) = repr mais curto; inteiro sai sem ".0".
"""

import math
from decimal import Decimal, ROUND_HALF_UP


def js_round(x):
    """JS Math.round: floor(x + 0.5)."""
    return math.floor(x + 0.5)


def round4(x):
    """GeometryUtils.round4: Math.round(n*10000)/10000."""
    return js_round(x * 10000) / 10000


def js_tofixed(x, nd=3):
    """Number.prototype.toFixed(nd) como o V8 realmente faz: opera sobre o
    valor exato do double e arredonda empate SEMPRE afastando do zero
    (ROUND_HALF_UP nos dois sinais — ex.: -37.9375 -> -37.938, -0.0625 ->
    -0.063). Nao segue a letra do spec ('maior n'), segue o V8."""
    d = Decimal(0) if x == 0 else Decimal(x)  # exato; normaliza -0.0 -> 0
    q = Decimal(1).scaleb(-nd)                # 10^-nd
    return str(d.quantize(q, rounding=ROUND_HALF_UP))


def js_num(x):
    """Stringificacao de numero como em `${x}` no JS: inteiro sem casas
    decimais, senao o repr mais curto que arredonda de volta (== repr do
    CPython para doubles)."""
    if isinstance(x, bool):
        return "true" if x else "false"
    f = float(x)
    if math.isinf(f) or math.isnan(f):
        return repr(f)
    if f == int(f):
        return str(int(f))
    return repr(f)
