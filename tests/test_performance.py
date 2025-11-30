# test_performance.py
# Test de rendimiento simple (carga media) para generate_templates_from_csv

import pandas as pd
from utils.narrative import generate_templates_from_csv


def test_performance_templates_dataset_medio(tmp_path):
    """Test de rendimiento: la función soporta un dataset mediano sin fallar."""

    # Dataset de tamaño medio (5000 filas)
    n = 5000
    df = pd.DataFrame({
        "estructuraalumno": ["A"] * n,
        "semestre": ["2024-1"] * n,
        "nota": list(range(n))
    })

    csv_path = tmp_path / "datos_perf.csv"
    df.to_csv(csv_path, index=False)

    with open(csv_path, "rb") as f:
        gallery, log, saved_paths = generate_templates_from_csv(
            file=f,
            chart_types=["Montaña"],     # 1 gráfico para no demorar tanto
            theme="light",
            group_col="estructuraalumno",
            metric_col="nota",
            heatmap_row="estructuraalumno",
            heatmap_col="semestre",
            line_x="semestre",
            line_y="nota",
            top_n=5,
            normalize=False,
            custom_title="Rendimiento",
            subtitle_hint="Dataset medio",
            simple_mode=True,
        )

    # No medimos tiempo exacto, pero verificamos que NO falle y genere al menos una imagen
    assert len(saved_paths) >= 1
