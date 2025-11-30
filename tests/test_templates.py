# test_templates.py
# Test de generación de plantillas (funcional) para generate_templates_from_csv

import os
from utils.narrative import generate_templates_from_csv


def test_generate_templates_barras_pastel_ok(tmp_path):
    """Test funcional: genera al menos una infografía (Barras/Pastel)."""

    csv_path = tmp_path / "datos_tpl.csv"
    csv_path.write_text(
        "estructuraalumno,semestre,nota\n"
        "A,2024-1,15\n"
        "B,2024-1,12\n"
        "C,2024-1,17\n"
    )

    with open(csv_path, "rb") as f:
        gallery, log, saved_paths = generate_templates_from_csv(
            file=f,
            chart_types=["Barras", "Pastel"],
            theme="light",
            group_col="estructuraalumno",
            metric_col="nota",
            heatmap_row="estructuraalumno",
            heatmap_col="semestre",
            line_x="semestre",
            line_y="nota",
            top_n=3,
            normalize=False,
            custom_title="Plantillas prueba",
            subtitle_hint="Subtítulo",
            simple_mode=True,
        )

    assert len(saved_paths) >= 1
    for p in saved_paths:
        assert os.path.exists(p)


def test_generate_templates_columna_incorrecta(tmp_path):
    """Test de manejo de errores: si el 'group_col' no existe, devuelve mensaje de error adecuado."""

    csv_path = tmp_path / "datos_tpl_err.csv"
    csv_path.write_text(
        "estructuraalumno,nota\n"
        "A,15\n"
        "B,12\n"
    )

    with open(csv_path, "rb") as f:
        gallery, log, saved_paths = generate_templates_from_csv(
            file=f,
            chart_types=["Barras"],
            theme="light",
            group_col="columna_inexistente",   # fuerza error
            metric_col="nota",
            heatmap_row="estructuraalumno",
            heatmap_col="semestre",
            line_x="semestre",
            line_y="nota",
            top_n=3,
            normalize=False,
            custom_title="Prueba error",
            subtitle_hint="",
            simple_mode=True,
        )

    assert saved_paths == []
    assert "Verifica 'Agrupar por' y 'Métrica'" in log
