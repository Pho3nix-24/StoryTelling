# test_structure.py
# Test de verificación de estructura del proyecto (archivos y carpetas clave)

import os


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_estructura_directorios_principales():
    """Test de estructura: existen las carpetas clave del proyecto."""
    for dirname in ["utils", "templates", "static", "output_images"]:
        path = os.path.join(BASE_DIR, dirname)
        assert os.path.isdir(path), f"Falta el directorio: {dirname}"


def test_estructura_archivos_principales():
    """Test de estructura: existen archivos Python y de requisitos clave."""
    for filename in ["app.py", "config.py", "requirements.txt"]:
        path = os.path.join(BASE_DIR, filename)
        assert os.path.isfile(path), f"Falta el archivo: {filename}"


def test_estructura_modulos_utils():
    """Test de estructura: módulos esenciales en utils/."""
    utils_dir = os.path.join(BASE_DIR, "utils")
    for filename in ["narrative.py", "charts.py", "data_processing.py", "__init__.py"]:
        path = os.path.join(utils_dir, filename)
        assert os.path.isfile(path), f"Falta utils/{filename}"
