"""Backend del módulo de alertas tempranas.

Expone el pipeline de ML existente (src/) como una API segura. Al importar el
paquete se agrega `src/` al path para reutilizar los modelos ya entrenados.
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
SRC = BACKEND.parent / "src"
for ruta in (str(SRC), str(BACKEND)):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
