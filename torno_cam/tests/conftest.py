import os
import sys

# Garante que a raiz do config (pai de torno_cam/) esteja no sys.path, para
# `import torno_cam...` funcionar rodando pytest de qualquer diretorio.
_CONFIG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _CONFIG_ROOT not in sys.path:
    sys.path.insert(0, _CONFIG_ROOT)
