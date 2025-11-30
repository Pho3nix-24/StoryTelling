from flask import Flask, request, jsonify, render_template, send_file
import os, shutil
import pandas as pd
import numpy as np
from config import OUTPUT_DIR
from utils.data_processing import (
    read_csv_smart, summary_table, detect_group_anomalies, 
    detect_row_anomalies, valid_numeric_cols, group_candidates,
    infer_rate
)
from utils.narrative import (
    get_ai_insights, # <-- ¡NUEVA FUNCIÓN DE IA!
    generate_native_sequence_6steps,
    generate_templates_from_csv
)
# ¡NUEVA IMPORTACIÓN! Necesitamos _agg_topn para el prompt
from utils.charts import _agg_topn 

app = Flask(__name__, template_folder='templates', static_folder='static')

def table_when_empty(anom_tab, method, k_iqr, z_thr, mad_thr, min_n):
    if anom_tab is None or anom_tab.empty:
        return pd.DataFrame({
            "mensaje": ["0 patrones anómalos detectados con los parámetros actuales"],
            "metodo": [method],
            "k_iqr": [k_iqr], "z_thr": [z_thr],
            "mad_thr": [mad_thr], "min_n": [min_n]
        })
    return anom_tab

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        file = request.files['file']
        if not file:
            return jsonify({'error': 'No se subió ningún archivo'}), 400
            
        df = read_csv_smart(file, nrows=None)
        file.seek(0) 
        head_df = read_csv_smart(file, nrows=8)
        head_df = head_df.replace([np.nan], [None])
        head = head_df.to_dict(orient='records')
        
        schema_df = summary_table(df)
        schema_df = schema_df.replace([np.nan], [None])
        schema = schema_df.to_dict(orient='records')
        
        method = request.form.get('method', 'iqr')
        group_col = request.form.get('group_col', 'estructuraalumno')
        metric_choice = request.form.get('metric_choice', '__tasa__')
        k_iqr = float(request.form.get('k_iqr', 1.5))
        z_thr = float(request.form.get('z_thr', 2.5))
        mad_thr = float(request.form.get('mad_thr', 3.5))
        min_n = int(request.form.get('min_n', 30))
        iso_frac = float(request.form.get('iso_frac', 0.02))
        
        # Necesitamos el df con la métrica calculada para el análisis
        df_analyzed = df.copy()
        if metric_choice == "__tasa__":
            tasa = infer_rate(df_analyzed)
            if tasa is not None:
                df_analyzed = df_analyzed.assign(__tasa__=tasa)
            else:
                # Si __tasa__ falla, no podemos analizar con ella
                metric_choice = valid_numeric_cols(df)[0] # Usar la primera métrica válida
        
        anom_tab_raw = detect_group_anomalies(df_analyzed, group_col, metric_choice, method, k_iqr, z_thr, mad_thr, min_n)
        anom_tab_display = table_when_empty(anom_tab_raw, method, k_iqr, z_thr, mad_thr, min_n)
        anom_tab_display = anom_tab_display.replace([np.nan], [None])
        anom_tab = anom_tab_display.to_dict(orient='records')
        
        iso_tab_raw = detect_row_anomalies(df, frac=iso_frac) if iso_frac > 0 else pd.DataFrame()
        iso_tab_raw = iso_tab_raw.replace([np.nan], [None])
        iso_tab = iso_tab_raw.to_dict(orient='records') if not iso_tab_raw.empty else []
        
        metrics = ["__tasa__"] + valid_numeric_cols(df)
        groups = group_candidates(df)
        
        return jsonify({
            'head': head,
            'schema': schema,
            'anom': anom_tab,
            'iso': iso_tab,
            'metrics': metrics,
            'groups': groups
        })
    except Exception as e:
        return jsonify({'error': f'Error en análisis: {str(e)}'}), 500

@app.route('/generate_sequence', methods=['POST'])
def generate_sequence():
    try:
        file = request.files['file']
        if not file:
            return jsonify({'error': 'No se subió ningún archivo'}), 400
        
        theme = request.form.get('seq_theme', 'light') 
        group_col = request.form.get('group_col', 'estructuraalumno')
        metric_col = request.form.get('metric_choice', '__tasa__')
        heatmap_row = request.form.get('seq_hm_row', 'estructuraalumno')
        heatmap_col = request.form.get('seq_hm_col', 'semestre')
        line_x = request.form.get('seq_line_x', 'semestre')
        line_y = request.form.get('seq_line_y', '__tasa__')
        top_n = int(request.form.get('seq_topn', 8))
        normalize = request.form.get('seq_norm') == 'on'
        title = request.form.get('seq_title', 'Rendimiento Académico')
        subtitle = request.form.get('seq_subt', 'Secuencia de comprensión visual')
        simple_mode = request.form.get('seq_simple') == 'on'
        
        # file.seek(0) # Rebobina el archivo para que la función pueda leerlo
        gallery_items, log, saved_paths, captions = generate_native_sequence_6steps(
            file, theme, group_col, metric_col, heatmap_row, heatmap_col, 
            line_x, line_y, top_n, normalize, title, subtitle, simple_mode
        )
        
        image_urls = [f'/output_images/{os.path.basename(path)}' for path in saved_paths]
        
        return jsonify({
            'images': image_urls,
            'captions': captions,
            'log': log
        })
    except Exception as e:
        return jsonify({'error': f'Error en secuencia: {str(e)}'}), 500

# ----------------------------------------------------------------------
# ¡ENDPOINT DE HISTORIA ACTUALIZADO PARA USAR IA!
# ----------------------------------------------------------------------
@app.route('/generate_story', methods=['POST'])
def generate_story():
    try:
        file = request.files['file']
        if not file:
            return jsonify({'error': 'No se subió ningún archivo'}), 400
        
        df = read_csv_smart(file)
        
        # Obtener los mismos parámetros de análisis que usa el frontend
        group_col = request.form.get('group_col', 'estructuraalumno')
        metric_choice = request.form.get('metric_choice', '__tasa__')
        method = request.form.get('method', 'iqr')
        k_iqr = float(request.form.get('k_iqr', 1.5))
        z_thr = float(request.form.get('z_thr', 2.5))
        mad_thr = float(request.form.get('mad_thr', 3.5))
        min_n = int(request.form.get('min_n', 30))
        top_n = int(request.form.get('seq_topn', 8)) # Tomar el Top N de la secuencia
        
        # --- RECOLECTAR DATOS PARA LA IA ---
        
        # 1. El Esquema (Schema)
        schema_df = summary_table(df)
        
        # 2. Las Anomalías (Anom Tab)
        df_analyzed = df.copy()
        if metric_choice == "__tasa__":
            tasa = infer_rate(df_analyzed)
            if tasa is not None:
                df_analyzed = df_analyzed.assign(__tasa__=tasa)
            else:
                metric_choice = valid_numeric_cols(df)[0] # Fallback
        
        anom_tab = detect_group_anomalies(df_analyzed, group_col, metric_choice, method, k_iqr, z_thr, mad_thr, min_n)
        
        # 3. Los Top N (Bar Data)
        bar_data = _agg_topn(df_analyzed, group_col, metric_choice, top_n=top_n)
        
        # --- LLAMAR AL AGENTE DE IA ---
        story_markdown = get_ai_insights(schema_df, anom_tab, bar_data)
        
        return jsonify({'story': story_markdown})
    
    except Exception as e:
        return jsonify({'error': f'Error en historia: {str(e)}'}), 500
# ----------------------------------------------------------------------

@app.route('/generate_templates', methods=['POST'])
def generate_templates():
    try:
        file = request.files['file']
        if not file:
            return jsonify({'error': 'No se subió ningún archivo'}), 400

        chart_types = request.form.getlist('tpl_chart_types[]') # Asegúrate que el JS envíe 'tpl_chart_types[]'
        theme = request.form.get('tpl_theme', 'light')
        group_col = request.form.get('tpl_group_col', 'estructuraalumno')
        metric_col = request.form.get('tpl_metric_col', '__tasa__')
        heatmap_row = request.form.get('tpl_hm_row', 'estructuraalumno')
        heatmap_col = request.form.get('tpl_hm_col', 'semestre')
        line_x = request.form.get('tpl_line_x', 'semestre')
        line_y = request.form.get('tpl_line_y', '__tasa__')
        top_n = int(request.form.get('tpl_topn', 8))
        normalize = request.form.get('tpl_norm') == 'on'
        title = request.form.get('tpl_title', 'Rendimiento Académico')
        subtitle = request.form.get('tpl_subtitle', 'Resumen visual desde dataset')
        simple_mode = request.form.get('tpl_simple') == 'on'

        gallery_items, log, saved_paths = generate_templates_from_csv(
            file, chart_types, theme, group_col, metric_col,
            heatmap_row, heatmap_col, line_x, line_y,
            top_n, normalize, title, subtitle, simple_mode
        )
        
        image_urls = [f'/output_images/{os.path.basename(path)}' for path in saved_paths]
        captions = [item[1] for item in gallery_items]
        
        return jsonify({
            'images': image_urls,
            'captions': captions,
            'log': log
        })
    except Exception as e:
        return jsonify({'error': f'Error en plantillas: {str(e)}'}), 500

@app.route('/download_zip', methods=['GET'])
def download_zip():
    try:
        zip_path_base = 'infografias' 
        zip_path_full = f"{zip_path_base}.zip"

        if os.path.exists(zip_path_full):
            os.remove(zip_path_full)
        
        shutil.make_archive(zip_path_base, 'zip', OUTPUT_DIR)
        
        return send_file(zip_path_full, as_attachment=True)
    except Exception as e:
        print(f'Error en ZIP: {str(e)}')
        return "Error generando ZIP", 500

@app.route('/output_images/<filename>')
def output_images(filename):
    response = send_file(os.path.join(OUTPUT_DIR, filename))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    app.run(debug=True)