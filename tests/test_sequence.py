# test_sequence.py
# Test de generación de secuencia nativa de 6 pasos (funcional / integración)

import os
from utils.narrative import generate_native_sequence_6steps


def test_generate_sequence_6steps_ok(tmp_path):
    """Test funcional: genera las 6 imágenes de la secuencia correctamente."""

    # CSV sencillo de prueba
    csv_path = tmp_path / "datos_seq.csv"
    csv_path.write_text(
        "estructuraalumno,semestre,nota\n"
        "A,2024-1,15\n"
        "A,2024-2,16\n"
        "B,2024-1,12\n"
    )

    with open(csv_path, "rb") as f:
        gallery, log, saved_paths, captions = generate_native_sequence_6steps(
            file=f,
            theme="light",
            group_col="estructuraalumno",
            metric_col="nota",
            heatmap_row="estructuraalumno",
            heatmap_col="semestre",
            line_x="semestre",
            line_y="nota",
            top_n=3,
            normalize=False,
            title="Prueba",
            subtitle="Secuencia de prueba",
            simple_mode=True,
        )

    assert len(saved_paths) == 6
    assert len(captions) == 6
    for p in saved_paths:
        assert os.path.exists(p)


def test_generate_sequence_error_tasa(tmp_path):
    """Test de manejo de errores: si se pide __tasa__ y no se puede calcular, devuelve mensaje de error."""

    # CSV sin columnas suficientes para calcular tasa
    csv_path = tmp_path / "datos_seq_simple.csv"
    csv_path.write_text(
        "estructuraalumno,nota\n"
        "A,15\n"
        "B,12\n"
    )

    with open(csv_path, "rb") as f:
        gallery, log, saved_paths, captions = generate_native_sequence_6steps(
            file=f,
            theme="light",
            group_col="estructuraalumno",
            metric_col="__tasa__",          # forzamos uso de tasa
            heatmap_row="estructuraalumno",
            heatmap_col="semestre",         # no existe
            line_x="semestre",
            line_y="__tasa__",
            top_n=3,
            normalize=False,
            title="Prueba tasa",
            subtitle="",
            simple_mode=True,
        )

    assert saved_paths == []
    assert "No se pudo calcular __tasa__" in log
