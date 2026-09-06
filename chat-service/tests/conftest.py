import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_RAIZ, os.path.join(_RAIZ, 'app'), os.path.join(_RAIZ, 'shims')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
