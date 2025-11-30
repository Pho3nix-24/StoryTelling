# conftest.py
# Configuración común para TODOS los tests (ruta raíz en PYTHONPATH)

import sys
import os

# Agregar el directorio raíz del proyecto a PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
