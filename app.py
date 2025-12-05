from flask import Flask, request, jsonify, render_template, send_file, session, redirect, url_for
import os, shutil
import pandas as pd
import numpy as np
import functools 
import hashlib # Para hashear contraseñas
import time # Para timestamp de registro
import json # Para cargar/guardar usuarios y parsear la respuesta de la IA
import re # Para parsear el bloque JSON de la IA
from config import OUTPUT_DIR, SECRET_KEY 
from utils.data_processing import (
    read_csv_smart, summary_table, detect_group_anomalies, 
    detect_row_anomalies, valid_numeric_cols, group_candidates,
    infer_rate
)
from utils.narrative import (
    get_ai_insights,
    generate_native_sequence_6steps,
    generate_templates_from_csv
)
from utils.charts import _agg_topn, chart_bar, chart_pie, chart_line, chart_heatmap, chart_violin, chart_montana, make_infographic_from_chart # Importa todas las funciones de gráfico

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = SECRET_KEY 

# --- FIREBASE / FIRESTORE SETUP ---

USER_DB_PATH = os.path.join(OUTPUT_DIR, "users.json")

def load_users():
    """Loads users from the local JSON file (simulating Firestore/DB)."""
    if not os.path.exists(USER_DB_PATH):
        # Default user for easy access
        return {"admin": {"password_hash": hashlib.sha256("password123".encode()).hexdigest(), "created_at": time.time()}}
    try:
        with open(USER_DB_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users):
    """Saves users to the local JSON file."""
    try:
        with open(USER_DB_PATH, 'w') as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        print(f"Error saving user data: {e}")

save_users(load_users()) # Initialize DB file

# --- Helper de Autenticación (Decorator) ---
def requires_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        # Checks if the user is logged in
        if 'logged_in' not in session or session['logged_in'] is not True:
            return redirect(url_for('login')) 
        return f(*args, **kwargs)
    return decorated
# -------------------------------------------

def table_when_empty(anom_tab, method, k_iqr, z_thr, mad_thr, min_n):
    if anom_tab is None or anom_tab.empty:
        return pd.DataFrame({
            "mensaje": ["0 patrones anómalos detectados con los parámetros actuales"],
            "metodo": [method],
            "k_iqr": [k_iqr], "z_thr": [z_thr],
            "mad_thr": [mad_thr], "min_n": [min_n]
        })
    return anom_tab

# --- HELPER DE VALIDACIÓN DE ARCHIVO ---
def validate_file_extension(file):
    if not file:
        return "No se subió ningún archivo."
    filename = file.filename
    if not filename.lower().endswith('.csv'):
        return "Tipo de archivo inválido. Por favor, sube solo archivos CSV (.csv)."
    return None

@app.route('/')
@requires_auth 
def index():
    return render_template('index.html', page='analyze-section') 

# --- RUTAS DE AUTENTICACIÓN ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()
        
        # Validación de credenciales
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        if username in users and users[username]['password_hash'] == hashed_password:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        else:
            error = 'Credenciales inválidas. Usuario o contraseña incorrectos.'
    
    if session.get('logged_in'):
        return redirect(url_for('index'))

    # Pasa el modo al template para mostrar el formulario de login por defecto
    return render_template('login.html', error=error, mode='login')


@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    error = None
    
    if not username or not password:
        error = "Usuario y contraseña son requeridos."
    else:
        users = load_users()
        if username in users:
            error = f"El usuario '{username}' ya existe."
        elif len(password) < 6:
            error = "La contraseña debe tener al menos 6 caracteres."
        else:
            # Hash y registro de nuevo usuario
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            users[username] = {"password_hash": hashed_password, "created_at": time.time()}
            save_users(users)
            
            # Inicia sesión inmediatamente después del registro
            session['logged_in'] = True
            session['username'] = username
            return jsonify({'success': True, 'redirect_url': url_for('index')})
            
    # Si hay error en el registro, retorna JSON con el error para el frontend
    if error:
        return jsonify({'error': error}), 400
        
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login'))

# --- RUTAS DE APLICACIÓN (PROTEGIDAS) ---

@app.route('/analyze', methods=['POST'])
@requires_auth
def analyze():
    try:
        file = request.files.get('file')
        error_msg = validate_file_extension(file)
        if error_msg:
            return jsonify({'error': error_msg}), 400
            
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
        
        df_analyzed = df.copy()
        
        # Handle metric calculation and fallback
        if metric_choice == "__tasa__":
            tasa = infer_rate(df_analyzed)
            if tasa is not None:
                df_analyzed = df_analyzed.assign(__tasa__=tasa)
            else:
                numeric_cols = valid_numeric_cols(df)
                if numeric_cols:
                     metric_choice = numeric_cols[0]
                else:
                     raise ValueError("No hay columnas numéricas válidas para la métrica.")
        
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
            'groups': groups,
            'current_metric': metric_choice
        })
    except Exception as e:
        return jsonify({'error': f'Error en análisis: {str(e)}'}), 500

@app.route('/generate_sequence', methods=['POST'])
@requires_auth
def generate_sequence():
    try:
        file = request.files.get('file')
        error_msg = validate_file_extension(file)
        if error_msg:
            return jsonify({'error': error_msg}), 400
        
        theme = request.form.get('seq_theme', 'light') 
        group_col = request.form.get('group_col', 'estructuraalumno')
        metric_col = request.form.get('metric_choice', '__tasa__')
        heatmap_row = request.form.get('seq_hm_row', 'estructuraalumno')
        heatmap_col = request.form.get('seq_hm_col', 'semestre')
        line_x = request.form.get('seq_line_x', 'semestre')
        line_y = request.form.get('seq_line_y', '__tasa__')
        top_n = int(request.form.get('seq_topn', 8))
        normalize = request.form.get('seq_norm') == 'on'
        
        # --- FIX GENERIC TITLES (Issue 1) ---
        default_title = f"Análisis de {metric_col} por {group_col}"
        title = request.form.get('seq_title', default_title)
        default_subtitle = f'Secuencia de visualización para {metric_col}'
        subtitle = request.form.get('seq_subt', default_subtitle)
        
        simple_mode = request.form.get('seq_simple') == 'on'
        
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

@app.route('/generate_story', methods=['POST'])
@requires_auth
def generate_story():
    try:
        file = request.files.get('file')
        error_msg = validate_file_extension(file)
        if error_msg:
            return jsonify({'error': error_msg}), 400
        
        df = read_csv_smart(file)
        
        group_col = request.form.get('group_col', 'estructuraalumno')
        metric_choice = request.form.get('metric_choice', '__tasa__')
        method = request.form.get('method', 'iqr')
        k_iqr = float(request.form.get('k_iqr', 1.5))
        z_thr = float(request.form.get('z_thr', 2.5))
        mad_thr = float(request.form.get('mad_thr', 3.5))
        min_n = int(request.form.get('min_n', 30))
        top_n = int(request.form.get('seq_topn', 8))
        
        # --- COLLECT DATA FOR AI ---
        schema_df = summary_table(df)
        
        df_analyzed = df.copy()
        
        # *** CLAVE: Asegurar la métrica correcta y manejar fallbacks antes de IA/Guardar ***
        valid_metric = metric_choice # Usamos el valor del formulario como base
        if metric_choice == "__tasa__":
            tasa = infer_rate(df_analyzed)
            if tasa is not None:
                df_analyzed = df_analyzed.assign(__tasa__=tasa)
            else:
                 # Fallback to first numeric if tasa fails
                numeric_cols = valid_numeric_cols(df)
                valid_metric = numeric_cols[0] if numeric_cols else 'N/A' # Actualizamos la métrica válida
        
        anom_tab = detect_group_anomalies(df_analyzed, group_col, valid_metric, method, k_iqr, z_thr, mad_thr, min_n)
        bar_data = _agg_topn(df_analyzed, group_col, valid_metric, top_n=top_n)
        
        # --- CALL AI AGENT (Receives story and chart recommendations) ---
        story_full_response = get_ai_insights(schema_df, anom_tab, bar_data)
        
        # --- NEW: Parse the full response to separate story from chart recommendations ---
        story_markdown = story_full_response
        chart_reco_json = []

        # Regex para encontrar el bloque JSON con la etiqueta charts_reco
        match = re.search(r"```charts_reco\s*(\[.*?\])\s*```", story_full_response, re.DOTALL)
        
        if match:
            json_str = match.group(1)
            # Quitar el bloque JSON de la historia para el frontend
            story_markdown = story_full_response.replace(match.group(0), "").strip()
            try:
                chart_reco_json = json.loads(json_str)
            except json.JSONDecodeError:
                print(f"Error parsing AI chart recommendation JSON: {json_str}")
                chart_reco_json = []

        # 1. Save analysis parameters and the new dynamic chart list
        session['last_analysis'] = {
            'group_col': group_col,
            'metric_choice': valid_metric, # <-- Guardamos la métrica YA VALIDADA/CORREGIDA
            'top_n': top_n,
            'theme': request.form.get('seq_theme', 'light'), 
            'simple_mode': request.form.get('seq_simple') == 'on',
            'line_x': request.form.get('seq_line_x', 'semestre'), 
            'line_y': request.form.get('seq_line_y', valid_metric),
            'ai_chart_recos': chart_reco_json # <-- Lista de gráficos generados por insight
        }
        
        # 2. Save the CSV file to disk for easy retrieval by the next endpoint
        file.seek(0)
        temp_filename = f"temp_user_{session.get('username') or 'anon'}.csv"
        temp_filepath = os.path.join(OUTPUT_DIR, temp_filename)
        file.save(temp_filepath)
        session['temp_csv_path'] = temp_filepath

        return jsonify({'story': story_markdown})
    
    except Exception as e:
        return jsonify({'error': f'Error en historia: {str(e)}'}), 500

# ----------------------------------------------------------------------
# ENDPOINT TO GENERATE AI RECOMMENDED CHARTS (Dynamic based on AI output)
# ----------------------------------------------------------------------
@app.route('/generate_ai_charts', methods=['POST'])
@requires_auth
def generate_ai_charts():
    try:
        # 1. Retrieve saved file and parameters
        temp_filepath = session.get('temp_csv_path')
        analysis_params = session.get('last_analysis')

        if not temp_filepath or not analysis_params or not os.path.exists(temp_filepath):
             return jsonify({'error': 'Error: No se encontró el archivo CSV ni los parámetros de análisis. Ejecuta el análisis y la historia primero.'}), 400

        # Set metric default from session
        metric_col_session = analysis_params['metric_choice']

        # 2. Open the temporary file and read dataframe
        with open(temp_filepath, 'rb') as f:
            
            f.seek(0) 
            df = read_csv_smart(f)
            
            # Procesar métrica __tasa__ si aplica (para asegurar que esté calculada)
            if metric_col_session == "__tasa__":
                tasa = infer_rate(df)
                if tasa is not None:
                    df = df.assign(__tasa__=tasa)
                else:
                    # Fallback metric
                    numeric_cols = valid_numeric_cols(df)
                    metric_col_session = numeric_cols[0] if numeric_cols else 'N/A' 
            
            # Use sampled data for heavy charts like Violin/Montaña
            df_sampled = df.sample(min(30000, len(df)), random_state=42) 

            # 3. Determinar y generar gráficos por recomendación de la IA
            ai_chart_recos = analysis_params.get('ai_chart_recos')
            
            saved_paths, captions = [], []
            log_msgs = []
            timestamp = int(time.time() * 1000)
            
            # Fallback si no hay recomendaciones dinámicas (usa el comportamiento anterior)
            if not ai_chart_recos:
                 ai_chart_recos = [
                    {"chart_type": "Barras", "group_col": analysis_params['group_col'], "metric_col": metric_col_session, "caption": f"Rendimiento por {analysis_params['group_col']} (Default)"},
                    {"chart_type": "Líneas", "x_col": analysis_params['line_x'], "y_col": analysis_params['line_y'], "caption": "Tendencia histórica (Default)"}
                 ]
                 log_msgs.append("Advertencia: Se usaron gráficos de soporte por defecto (AI no devolvió recomendaciones dinámicas).")
            else:
                 log_msgs.append(f"Generando {len(ai_chart_recos)} gráficos basados en insights de IA.")

            theme = analysis_params['theme']
            simple_mode = analysis_params['simple_mode']
            top_n = analysis_params['top_n']
            
            for i, reco in enumerate(ai_chart_recos):
                chart_type = reco.get('chart_type')
                
                # Parámetros dinámicos con fallback
                group_col = reco.get('group_col') or analysis_params['group_col']
                metric_col = reco.get('metric_col') or metric_col_session # Use session metric as fallback
                line_x = reco.get('x_col') or analysis_params['line_x']
                line_y = reco.get('y_col') or metric_col
                heatmap_row = reco.get('row_col') or analysis_params['group_col']
                heatmap_col = reco.get('col_col') or analysis_params['line_x']
                caption_text = reco.get('caption') or f"{chart_type} de {metric_col}"

                fig = None
                
                # Lógica de generación de gráfico
                if chart_type == "Barras":
                    if group_col in df.columns and metric_col in df.columns:
                        agg = _agg_topn(df, group_col, metric_col, top_n=top_n)
                        if not agg.empty:
                            fig = chart_bar(agg, theme=theme, ylabel=metric_col, simple=simple_mode)
                elif chart_type == "Pastel":
                    if group_col in df.columns and metric_col in df.columns:
                        agg = _agg_topn(df, group_col, metric_col, top_n=top_n, normalize=True)
                        if not agg.empty:
                            fig = chart_pie(agg, theme=theme, simple=simple_mode)
                elif chart_type == "Líneas":
                    # For lines, ensure line_y (metric) is available
                    final_line_y = line_y if line_y in df.columns else metric_col
                    if line_x in df.columns and final_line_y in df.columns:
                        fig = chart_line(df, x_col=line_x, y_col=final_line_y, theme=theme, simple=simple_mode)
                elif chart_type == "Heatmap":
                     if heatmap_row in df.columns and heatmap_col in df.columns and metric_col in df.columns:
                         fig = chart_heatmap(
                            df, row_col=heatmap_row, col_col=heatmap_col, metric_col=metric_col, 
                            theme=theme, simple=simple_mode
                         )
                elif chart_type == "Violín":
                     if group_col in df.columns and metric_col in df.columns:
                         fig = chart_violin(
                            df_sampled, group_col=group_col, metric_col=metric_col, 
                            theme=theme, simple=simple_mode, top_n=top_n
                         )
                elif chart_type == "Montaña":
                     if metric_col in df.columns:
                         fig = chart_montana(df_sampled, metric_col=metric_col, theme=theme, simple=simple_mode)
                
                # Save and collect results if figure was created
                if fig:
                    chart_name = f"{chart_type.lower()}_{i}_{timestamp}.png"
                    pth = os.path.join(OUTPUT_DIR, chart_name)
                    
                    base_title = analysis_params.get('custom_title', f"Visualización de Soporte IA")
                    
                    make_infographic_from_chart(
                        fig, 
                        base_title, 
                        f"Gráfico de {chart_type}: {caption_text}", # Use the AI's caption here
                        "Fuente: dataset cargado · © Tu Proyecto", 
                        theme, 
                        pth
                    )
                    
                    saved_paths.append(os.path.abspath(pth))
                    captions.append(caption_text)
                    log_msgs.append(f"Gráfico de {chart_type} generado: {caption_text}")
                else:
                    log_msgs.append(f"Advertencia: No se pudo generar el gráfico de {chart_type} (columnas faltantes o datos insuficientes).")

        image_urls = [f'/output_images/{os.path.basename(p)}' for p in saved_paths]
        log = " | ".join(log_msgs) if log_msgs else "Gráficos de soporte generados correctamente."
        
        return jsonify({
            'images': image_urls,
            'captions': captions,
            'log': log
        })

    except Exception as e:
        # Check if the error is related to key not being defined in reco (e.g. keyerror)
        import traceback
        return jsonify({'error': f'Error generando gráficos de IA: {str(e)}\n{traceback.format_exc()}'}), 500
# ----------------------------------------------------------------------


@app.route('/download_zip', methods=['GET'])
@requires_auth # Quita esta línea si la descarga sigue fallando en Cloud Run.
def download_zip():
    try:
        # 1. Asegurar que OUTPUT_DIR exista antes de zipear
        if not os.path.exists(OUTPUT_DIR):
             return jsonify({'error': 'Error: No hay infografías generadas para descargar.'}), 404

        # --- Usamos /tmp para escritura segura ---
        temp_dir = '/tmp'
        zip_file_name = 'infografias.zip'
        
        # Definir la ruta COMPLETA del ZIP en /tmp
        zip_path_base = os.path.join(temp_dir, 'infografias')
        zip_path_full = os.path.join(temp_dir, zip_file_name)

        # Limpiar archivos previos
        if os.path.exists(zip_path_full):
            os.remove(zip_path_full)
        
        # Crear el ZIP: zipea el contenido de OUTPUT_DIR, el resultado queda en /tmp
        # 'zip' es el formato de archivo (zip)
        shutil.make_archive(zip_path_base, 'zip', OUTPUT_DIR)
        
        # Enviar el archivo
        return send_file(zip_path_full, as_attachment=True, download_name=zip_file_name)
    
    except Exception as e:
        # Este print es crucial para debuggear en los logs de Cloud Run
        print(f'Error CRÍTICO en ZIP: {type(e).__name__} - {str(e)}')
        return jsonify({'error': f'Error al generar o servir el ZIP. Detalles: {str(e)}'}), 500

@app.route('/output_images/<filename>')
@requires_auth
def output_images(filename):
    """Sirve los archivos de imagen generados (PNG/JPG) desde OUTPUT_DIR, con seguridad y cacheo deshabilitado."""
    try:
        full_path = os.path.join(OUTPUT_DIR, filename)
        
        # Validación de seguridad: Previene que el usuario acceda a archivos fuera de OUTPUT_DIR.
        # Usa el path absoluto normalizado para una comparación segura.
        if not os.path.abspath(full_path).startswith(os.path.abspath(OUTPUT_DIR)):
            return "Acceso no permitido", 403
            
        # Envía el archivo con el mimetype correcto
        response = send_file(full_path, mimetype='image/png')
        
        # Deshabilitar cache para asegurar que se vean los gráficos actualizados
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
    except FileNotFoundError:
        # Esto captura el error si send_file no encuentra el archivo
        return jsonify({'error': f'Archivo no encontrado: {filename}'}), 404
    except Exception as e:
        print(f"Error sirviendo imagen: {e}")
        return jsonify({'error': f'Error interno al servir el archivo: {str(e)}'}), 500
# -------------------------------------------------------------


if __name__ == '__main__':
    # Si estás ejecutando localmente en Windows, usa debug=True.
    # En la nube, usa el puerto de ambiente.
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
