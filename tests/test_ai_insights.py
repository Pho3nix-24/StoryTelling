# test_ai_insights.py
# Test de lógica de IA (unitario / caja blanca) para get_ai_insights

import pandas as pd
import utils.narrative as narrative


def test_get_ai_insights_devuelve_texto(monkeypatch):
    """Test de caja blanca: get_ai_insights devuelve texto Markdown usando un modelo mock."""

    # Dummy model para NO llamar a la API real de Gemini
    class DummyModel:
        def __init__(self, name):
            self.name = name

        def generate_content(self, prompt):
            class R:
                text = "### 🧠 Resumen Ejecutivo\nTexto de prueba IA"
            return R()

    # Reemplazamos GenerativeModel por nuestro dummy
    monkeypatch.setattr(narrative.genai, "GenerativeModel", DummyModel)

    # DataFrames mínimos para simular los insumos
    schema_df = pd.DataFrame({"columna": ["nota"], "tipo": ["int"]})
    anom_df = pd.DataFrame({"grupo": ["A"], "anomalia": ["⚠"]})
    bar_df = pd.DataFrame({"grupo": ["A"], "promedio": [15]}).set_index("grupo")

    texto = narrative.get_ai_insights(schema_df, anom_df, bar_df)

    assert isinstance(texto, str)
    assert "Resumen Ejecutivo" in texto


def test_get_ai_insights_sin_api_key(monkeypatch):
    """Test de manejo de errores: cuando no hay GEMINI_API_KEY devuelve mensaje controlado."""

    # Guardamos la key original y la dejamos vacía temporalmente
    original_key = narrative.GEMINI_API_KEY
    monkeypatch.setattr(narrative, "GEMINI_API_KEY", "")

    schema_df = pd.DataFrame({"columna": ["nota"], "tipo": ["int"]})
    anom_df = pd.DataFrame({"grupo": ["A"], "anomalia": ["⚠"]})
    bar_df = pd.DataFrame({"grupo": ["A"], "promedio": [15]}).set_index("grupo")

    texto = narrative.get_ai_insights(schema_df, anom_df, bar_df)

    assert "Falta la GEMINI_API_KEY" in texto

    # Restauramos la key original
    monkeypatch.setattr(narrative, "GEMINI_API_KEY", original_key)
