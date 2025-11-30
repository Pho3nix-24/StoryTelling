# test_api_endpoints.py
# Test de prueba de caja negra (endpoints HTTP de Flask)

from io import BytesIO
import pytest
from app import app


@pytest.fixture
def client():
    """Fixture: cliente de pruebas de Flask (caja negra)."""
    app.testing = True
    with app.test_client() as client:
        yield client


def test_index_responde_200(client):
    """Test de caja negra: la ruta raíz '/' responde 200 OK."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_analyze_con_csv_valido(client, tmp_path):
    """Test de caja negra: /analyze procesa un CSV válido y retorna JSON con claves esperadas."""

    csv_content = (
        "estructuraalumno,semestre,nota\n"
        "A,2024-1,15\n"
        "B,2024-1,12\n"
    )

    data = {
        "file": (BytesIO(csv_content.encode("utf-8")), "datos.csv"),
        # Opcional: podríamos agregar parámetros del formulario si se requiere
    }

    resp = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200

    payload = resp.get_json()
    # Claves principales que devuelve tu endpoint
    for key in ["head", "schema", "anom", "iso", "metrics", "groups"]:
        assert key in payload


def test_generate_sequence_endpoint(client, tmp_path):
    """Test de caja negra: /generate_sequence genera 6 imágenes y devuelve rutas."""

    csv_content = (
        "estructuraalumno,semestre,nota\n"
        "A,2024-1,15\n"
        "A,2024-2,16\n"
        "B,2024-1,12\n"
    )

    data = {
        "file": (BytesIO(csv_content.encode("utf-8")), "datos_seq.csv"),
        "seq_theme": "light",
        "group_col": "estructuraalumno",
        "metric_choice": "nota",
        "seq_hm_row": "estructuraalumno",
        "seq_hm_col": "semestre",
        "seq_line_x": "semestre",
        "seq_line_y": "nota",
        "seq_topn": "3",
    }

    resp = client.post("/generate_sequence", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200

    payload = resp.get_json()
    assert "images" in payload
    assert "captions" in payload
    assert len(payload["images"]) == 6
    assert len(payload["captions"]) == 6
