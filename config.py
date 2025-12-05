import os

# ----------------------------------------------------------------------
# CLAVE DE API PARA GEMINI
# ----------------------------------------------------------------------
# ⚠ IMPORTANTE:
# - No uses la clave anterior que pegaste (ya se considera comprometida).
# - Entra a Google AI Studio, genera una NUEVA API key
#   y reemplaza el texto "TU_NUEVA_API_KEY_AQUI" por tu clave real.

GEMINI_API_KEY = "---------------------------------------"  # ← reemplaza esto por tu nueva 
SECRET_KEY = os.environ.get('SECRET_KEY', 'una_clave_secreta_muy_larga_y_dificil')

# Carpeta donde se guardan las imágenes generadas
OUTPUT_DIR = "./output_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ----------------------------------------------------------------------
# THEMES (Movido desde el script de Gradio)
# ----------------------------------------------------------------------
THEMES = {
    "midnight": {
        "bg": (18, 22, 28),
        "fg": (240, 243, 247),
        "accent": (17, 185, 195),
        "muted": (90, 104, 120)
    },
    "teal-dark": {
        "bg": (6, 29, 33),
        "fg": (220, 230, 233),
        "accent": (0, 168, 150),
        "muted": (90, 110, 120)
    },
    "indigo": {
        "bg": (18, 18, 48),
        "fg": (235, 236, 255),
        "accent": (109, 119, 255),
        "muted": (120, 126, 168)
    },
    "light": {
        "bg": (246, 248, 251),
        "fg": (20, 24, 28),
        "accent": (3, 138, 255),
        "muted": (120, 130, 140)
    },
    "black-orange": {
        "bg": (0, 0, 0),
        "fg": (255, 255, 255),
        "accent": (255, 165, 0),
        "muted": (80, 80, 80)
    }
}
