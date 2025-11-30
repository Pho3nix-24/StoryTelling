import pandas as pd
import numpy as np
import time
import os
from PIL import Image
import google.generativeai as genai

# Importaciones internas
from .data_processing import read_csv_smart, infer_rate
from .charts import (
    chart_bar, chart_pie, chart_line, chart_heatmap,
    chart_violin, chart_montana, make_infographic_from_chart,
    _agg_topn
)
from config import OUTPUT_DIR, GEMINI_API_KEY


# ============================================================
# 1) AGENTE DE IA – INSIGHTS CON GEMINI
# ============================================================

def get_ai_insights(schema_df, anom_df, bar_data_df):
    """
    Usa Gemini para generar una historia/insights a partir de:
    - schema_df: resumen de columnas
    - anom_df: tabla de anomalías por grupo
    - bar_data_df: top N grupos (para barras)
    """

    if not GEMINI_API_KEY or GEMINI_API_KEY.strip() == "":
        return (
            "**Error: Falta la GEMINI_API_KEY en `config.py`.**\n"
            "No se pudo contactar al agente de IA."
        )

    try:
        # Configurar API con tu clave
        genai.configure(api_key=GEMINI_API_KEY)

        # 🔥 Modelo que tu clave SÍ tiene habilitado (según listar_modelos.py)
        # En list_models aparece como: models/gemini-2.5-pro
        model = genai.GenerativeModel("gemini-2.5-pro")

        # Pasar dataframes a Markdown
        schema_md = schema_df.to_markdown(index=False)
        anom_md = anom_df.to_markdown(index=False)
        bar_md = bar_data_df.reset_index().to_markdown(index=False)

        prompt = f"""
        Eres un analista de datos senior.

        A continuación tienes el resultado de analizar un dataset:

        ## 1. ESQUEMA DEL ARCHIVO
        {schema_md}

        ## 2. ANOMALÍAS POR GRUPO
        {anom_md}

        ## 3. TOP N GRUPOS (RENDIMIENTO / MÉTRICA PRINCIPAL)
        {bar_md}

        Con base SOLO en esta información, responde en ESPAÑOL,
        en formato Markdown con la siguiente estructura:

        ### 🧠 Resumen Ejecutivo
        - (2–3 líneas con el hallazgo más importante)

        ### 🎯 Insights Clave
        - 3 a 5 puntos accionables, conectando anomalías y top N con posibles decisiones.

        ### 💡 Próximos Pasos
        - 2 a 3 recomendaciones concretas sobre qué debería hacer el usuario a continuación.
        """

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"**Error contactando a Gemini:** `{e}`"


# ============================================================
# 2) GENERADOR DE PLANTILLAS
# ============================================================

def generate_templates_from_csv(file, chart_types, theme, group_col, metric_col,
                                heatmap_row, heatmap_col, line_x, line_y,
                                top_n, normalize, custom_title, subtitle_hint,
                                simple_mode):
    """
    Genera infografías sueltas (plantillas) según los tipos de gráfico seleccionados.
    Devuelve:
        - gallery: lista de (PIL.Image, texto)
        - log: mensaje de log
        - saved: rutas absolutas de los PNG generados
    """
    if not chart_types:
        return [], "Selecciona al menos 1 tipo de gráfico.", []

    df = read_csv_smart(file).copy()

    # Procesar métrica __tasa__ si aplica
    if metric_col == "__tasa__":
        tasa = infer_rate(df)
        if tasa is None:
            return [], "No se pudo calcular __tasa__ (faltan columnas).", []
        df = df.assign(__tasa__=tasa)
        metric_col = "__tasa__"

    SAMPLE_LIMIT = 30000
    if len(df) > SAMPLE_LIMIT:
        df_sampled = df.sample(SAMPLE_LIMIT, random_state=42)
    else:
        df_sampled = df

    saved, gallery, msgs = [], [], []
    title = custom_title or f"Infografía: {metric_col}"
    subtitle = subtitle_hint or "Generado automáticamente a partir del CSV"
    footer = "Fuente: dataset cargado · © Tu Proyecto"
    timestamp = int(time.time() * 1000)

    # -------------------------------------------------------
    # BARRAS / PASTEL
    # -------------------------------------------------------
    if any(t in chart_types for t in ["Barras", "Pastel"]):
        if group_col not in df.columns or metric_col not in df.columns:
            return [], "Verifica 'Agrupar por' y 'Métrica'.", []
        agg = _agg_topn(df, group_col, metric_col, top_n=int(top_n))

        if "Barras" in chart_types:
            agg_bar = agg / agg.sum() if normalize and agg.sum() > 0 else agg
            fig = chart_bar(agg_bar, theme=theme, ylabel=metric_col, simple=simple_mode)
            pth = f"{OUTPUT_DIR}/templ_bar_{timestamp}.png"
            make_infographic_from_chart(
                fig, title,
                f"{subtitle} · Top {len(agg)} por {group_col}",
                footer, theme, pth
            )
            img = Image.open(pth).convert("RGB")
            saved.append(os.path.abspath(pth))
            gallery.append((img, f"Barras: {group_col}"))

        if "Pastel" in chart_types:
            agg_pie = _agg_topn(df, group_col, metric_col, top_n=int(top_n), normalize=True)
            fig = chart_pie(agg_pie, theme=theme, simple=simple_mode)
            pth = f"{OUTPUT_DIR}/templ_pie_{timestamp}.png"
            make_infographic_from_chart(
                fig, title,
                f"{subtitle} · Distribución {group_col}",
                footer, theme, pth
            )
            img = Image.open(pth).convert("RGB")
            saved.append(os.path.abspath(pth))
            gallery.append((img, f"Pastel: {group_col}"))

    # -------------------------------------------------------
    # LÍNEAS
    # -------------------------------------------------------
    if "Líneas" in chart_types:
        if (line_x not in df.columns) or (line_y not in df.columns):
            msgs.append("⚠ No se pudo crear Líneas: revisa 'Eje X' y 'Eje Y'.")
        else:
            fig = chart_line(df, x_col=line_x, y_col=line_y, theme=theme, simple=simple_mode)
            pth = f"{OUTPUT_DIR}/templ_line_{timestamp}.png"
            make_infographic_from_chart(
                fig, title,
                f"{subtitle} · {line_x} vs {line_y}",
                footer, theme, pth
            )
            img = Image.open(pth).convert("RGB")
            saved.append(os.path.abspath(pth))
            gallery.append((img, f"Líneas: {line_x}"))

    # -------------------------------------------------------
    # HEATMAP
    # -------------------------------------------------------
    if "Heatmap" in chart_types:
        if (heatmap_row not in df.columns) or (heatmap_col not in df.columns) or (metric_col not in df.columns):
            msgs.append("⚠ No se pudo crear Heatmap: revisa fila, columna y métrica.")
        else:
            fig = chart_heatmap(
                df,
                row_col=heatmap_row,
                col_col=heatmap_col,
                metric_col=metric_col,
                theme=theme,
                simple=simple_mode
            )
            pth = f"{OUTPUT_DIR}/templ_heat_{timestamp}.png"
            make_infographic_from_chart(
                fig, title,
                f"{subtitle} · {heatmap_row} × {heatmap_col}",
                footer, theme, pth
            )
            img = Image.open(pth).convert("RGB")
            saved.append(os.path.abspath(pth))
            gallery.append((img, f"Heatmap: {heatmap_row}×{heatmap_col}"))

    # -------------------------------------------------------
    # VIOLÍN
    # -------------------------------------------------------
    if "Violín" in chart_types:
        if (group_col not in df.columns) or (metric_col not in df.columns):
            msgs.append("⚠ No se pudo crear Violín: revisa 'Agrupar por' y 'Métrica'.")
        else:
            fig = chart_violin(
                df_sampled,
                group_col=group_col,
                metric_col=metric_col,
                theme=theme,
                simple=simple_mode,
                top_n=int(top_n)
            )
            pth = f"{OUTPUT_DIR}/templ_violin_{timestamp}.png"
            make_infographic_from_chart(
                fig, title,
                f"{subtitle} · Distribución por {group_col}",
                footer, theme, pth
            )
            img = Image.open(pth).convert("RGB")
            saved.append(os.path.abspath(pth))
            gallery.append((img, f"Violín: {group_col}"))

    # -------------------------------------------------------
    # MONTAÑA
    # -------------------------------------------------------
    if "Montaña" in chart_types:
        if metric_col not in df.columns:
            msgs.append("⚠ No se pudo crear Montaña: revisa 'Métrica'.")
        else:
            fig = chart_montana(df_sampled, metric_col=metric_col, theme=theme, simple=simple_mode)
            pth = f"{OUTPUT_DIR}/templ_montana_{timestamp}.png"
            make_infographic_from_chart(
                fig, title,
                f"{subtitle} · Mapa de la Montaña",
                footer, theme, pth
            )
            img = Image.open(pth).convert("RGB")
            saved.append(os.path.abspath(pth))
            gallery.append((img, "Montaña"))

    if not saved:
        msgs.append("⚠ No se generó ninguna infografía con los parámetros dados.")

    log = " • ".join(msgs) if msgs else "Plantillas generadas correctamente."
    return gallery, log, saved


# ============================================================
# 3) SECUENCIA NATIVA DE 6 PASOS
# ============================================================

def generate_native_sequence_6steps(file, theme, group_col, metric_col,
                                    heatmap_row, heatmap_col, line_x, line_y,
                                    top_n, normalize, title, subtitle, simple_mode):
    """
    Genera la secuencia de 6 pasos (barras, pastel, líneas, heatmap, violín, montaña).
    Devuelve:
        - gallery_items: lista de (PIL.Image, texto)
        - log: mensaje breve
        - saved_paths: rutas absolutas de los PNG generados
        - captions: textos para mostrar en frontend
    """
    df = read_csv_smart(file).copy()

    # Procesar __tasa__ si corresponde
    if metric_col == "__tasa__":
        tasa = infer_rate(df)
        if tasa is None:
            return [], "No se pudo calcular __tasa__ (faltan columnas).", [], []
        df = df.assign(__tasa__=tasa)
        metric_col = "__tasa__"

    SAMPLE_LIMIT = 30000
    if len(df) > SAMPLE_LIMIT:
        df_sampled = df.sample(SAMPLE_LIMIT, random_state=42)
    else:
        df_sampled = df

    saved_paths, gallery_items, captions = [], [], []
    footer = "Fuente: dataset cargado · © Tu Proyecto"
    title = title or "Rendimiento Académico"
    subtitle = subtitle or "Secuencia de comprensión visual"
    timestamp = int(time.time() * 1000)

    # Paso 1: Barras
    agg = _agg_topn(df, group_col, metric_col, top_n=int(top_n), normalize=False)
    fig = chart_bar(agg, theme=theme, ylabel=metric_col, simple=simple_mode)
    p1 = f"{OUTPUT_DIR}/seq_01_barras_{timestamp}.png"
    make_infographic_from_chart(fig, title, f"Paso 1 · Top {len(agg)} por {group_col}", footer, theme, p1)
    gallery_items.append((Image.open(p1).convert("RGB"), "Paso 1: Barras"))
    saved_paths.append(os.path.abspath(p1)); captions.append("Paso 1: Barras")

    # Paso 2: Pastel
    agg_pie = _agg_topn(df, group_col, metric_col, top_n=int(top_n), normalize=True)
    fig = chart_pie(agg_pie, theme=theme, simple=simple_mode)
    p2 = f"{OUTPUT_DIR}/seq_02_pastel_{timestamp}.png"
    make_infographic_from_chart(fig, title, f"Paso 2 · Distribución {group_col}", footer, theme, p2)
    gallery_items.append((Image.open(p2).convert("RGB"), "Paso 2: Pastel"))
    saved_paths.append(os.path.abspath(p2)); captions.append("Paso 2: Pastel")

    # Paso 3: Líneas
    fig = chart_line(df, x_col=line_x, y_col=line_y, theme=theme, simple=simple_mode)
    p3 = f"{OUTPUT_DIR}/seq_03_lineas_{timestamp}.png"
    make_infographic_from_chart(fig, title, f"Paso 3 · {line_x} vs {line_y}", footer, theme, p3)
    gallery_items.append((Image.open(p3).convert("RGB"), "Paso 3: Líneas"))
    saved_paths.append(os.path.abspath(p3)); captions.append("Paso 3: Líneas")

    # Paso 4: Heatmap
    fig = chart_heatmap(df, row_col=heatmap_row, col_col=heatmap_col, metric_col=metric_col, theme=theme, simple=simple_mode)
    p4 = f"{OUTPUT_DIR}/seq_04_heatmap_{timestamp}.png"
    make_infographic_from_chart(fig, title, f"Paso 4 · {heatmap_row} × {heatmap_col}", footer, theme, p4)
    gallery_items.append((Image.open(p4).convert("RGB"), "Paso 4: Heatmap"))
    saved_paths.append(os.path.abspath(p4)); captions.append("Paso 4: Heatmap")

    # Paso 5: Violín
    fig = chart_violin(df_sampled, group_col=group_col, metric_col=metric_col, theme=theme, simple=simple_mode, top_n=int(top_n))
    p5 = f"{OUTPUT_DIR}/seq_05_violin_{timestamp}.png"
    make_infographic_from_chart(fig, title, f"Paso 5 · Distribución por {group_col}", footer, theme, p5)
    gallery_items.append((Image.open(p5).convert("RGB"), "Paso 5: Violín"))
    saved_paths.append(os.path.abspath(p5)); captions.append("Paso 5: Violín")

    # Paso 6: Montaña
    fig = chart_montana(df_sampled, metric_col=metric_col, theme=theme, simple=simple_mode)
    p6 = f"{OUTPUT_DIR}/seq_06_montana_{timestamp}.png"
    make_infographic_from_chart(fig, title, "Paso 6 · Mapa de la Montaña", footer, theme, p6)
    gallery_items.append((Image.open(p6).convert("RGB"), "Paso 6: Montaña"))
    saved_paths.append(os.path.abspath(p6)); captions.append("Paso 6: Montaña")

    log = "Secuencia nativa generada (6 pasos)."
    return gallery_items, log, saved_paths, captions
