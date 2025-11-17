import matplotlib
matplotlib.use("Agg") # Importante para Flask
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde
import pandas as pd
import numpy as np
import io
import copy # <--- Necesario para la corrección del heatmap
from PIL import Image, ImageDraw, ImageFont

# Importa THEMES y OUTPUT_DIR desde tu config
from config import THEMES, OUTPUT_DIR

# ===== Estilo global grande =====
plt.rcParams.update({
    "font.size": 15,
    "axes.titlesize": 22,
    "axes.labelsize": 18,
    "xtick.labelsize": 15,
    "ytick.labelsize": 15,
    "legend.fontsize": 14
})

# --- CONFIGURACIÓN DE FUENTE DE PIL ---
try:
    PIL_FONT_TITLE = ImageFont.truetype("Arial.ttf", 60)
    PIL_FONT_SUBTITLE = ImageFont.truetype("Arial.ttf", 30)
    PIL_FONT_FOOTER = ImageFont.truetype("Arial.ttf", 22)
except IOError:
    print("Advertencia: Arial.ttf no encontrada. Usando fuente por defecto de PIL.")
    PIL_FONT_TITLE = ImageFont.load_default()
    PIL_FONT_SUBTITLE = ImageFont.load_default()
    PIL_FONT_FOOTER = ImageFont.load_default()

# --------------------------------------------------------------------------------------------------
# HELPERS DE GRAFICACIÓN (La versión simple original)
# --------------------------------------------------------------------------------------------------

def _to_rgb01(rgb_tuple): return tuple([c/255.0 for c in rgb_tuple])
def _ensure_num(s): return pd.to_numeric(s, errors="coerce")

def _agg_topn(df, group_col, metric_col, top_n=8, normalize=False):
    g = (df[[group_col, metric_col]]
         .assign(**{metric_col: _ensure_num(df[metric_col])})
         .dropna()
         .groupby(group_col)[metric_col].mean().sort_values(ascending=False))
    if top_n and top_n > 0: g = g.head(int(top_n))
    if normalize and g.sum() > 0: g = g / g.sum()
    return g

def _canvas(width=1600, height=900, theme="light"):
    colors = THEMES.get(theme, THEMES["light"])
    img = Image.new("RGB", (width, height), color=colors["bg"])
    draw = ImageDraw.Draw(img); return img, draw, colors

def _draw_header(draw, colors, title, subtitle, width=1600, pad=32):
    draw.text((pad, pad), title, fill=colors["fg"], font=PIL_FONT_TITLE)
    draw.text((pad, pad + PIL_FONT_TITLE.getbbox(title)[3] + 10), subtitle, fill=colors["muted"], font=PIL_FONT_SUBTITLE)

def _draw_footer(draw, colors, footer, width=1600, height=900, pad=28):
    try:
        bbox = draw.textbbox((0, 0), footer, font=PIL_FONT_FOOTER)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except AttributeError:
        tw, th = draw.textsize(footer, font=PIL_FONT_FOOTER)
    draw.text((width - tw - pad, height - th - pad), footer, fill=colors["muted"], font=PIL_FONT_FOOTER)

def _paste_plot_on_canvas(fig, canvas_img, bbox=(80, 180, 1520, 820), dpi=100): # DPI optimizado
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig); buf.seek(0)
    plot_img = Image.open(buf).convert("RGBA")
    x1,y1,x2,y2 = bbox; w,h = x2-x1, y2-y1
    plot_img = plot_img.resize((w,h), Image.LANCZOS)
    frame = Image.new("RGBA",(w,h),(0,0,0,0)); frame.paste(plot_img,(0,0),plot_img)
    canvas_img.paste(frame,(x1,y1),frame); return canvas_img

def _bubble(ax, xy, text, xytext, color="lightgreen", textcoords="axes fraction"):
    ax.annotate(text, xy=xy, xytext=xytext,
        textcoords=textcoords,
        arrowprops=dict(arrowstyle="->", lw=2, color="black"),
        bbox=dict(boxstyle="round,pad=0.5", fc=color, ec="black", alpha=0.9),
        fontsize=10) 

# --------------------------------------------------------------------------------------------------
# FUNCIONES DE GRÁFICOS (Con corrección de heatmap)
# --------------------------------------------------------------------------------------------------

def chart_bar(g_series, theme="light", ylabel="", simple=False):
    colors = THEMES.get(theme, THEMES["light"])
    fig = plt.figure(figsize=(10,6), facecolor=_to_rgb01(colors["bg"])); ax = fig.add_subplot(111)
    ax.set_facecolor(_to_rgb01(colors["bg"]))
    bars = ax.bar(g_series.index.astype(str), g_series.values, color=_to_rgb01(colors["accent"]))
    
    ax.tick_params(axis='x', labelrotation=45, labelsize=9)
    plt.setp(ax.get_xticklabels(), ha="right", rotation_mode="anchor") 
    
    ax.tick_params(axis='y', colors=_to_rgb01(colors["fg"]), labelsize=10)
    ax.spines['bottom'].set_color(_to_rgb01(colors["muted"])); ax.spines['left'].set_color(_to_rgb01(colors["muted"]))
    ax.set_ylabel(ylabel, color=_to_rgb01(colors["fg"]))
    for b in bars:
        v = b.get_height()
        ax.text(b.get_x()+b.get_width()/2, v, f"{v:,.2f}", ha="center", va="bottom",
                color=_to_rgb01(colors["fg"]), fontsize=12, fontweight="bold")
    if simple and len(bars)>0:
        bmax = max(bars, key=lambda b: b.get_height())
        bmin = min(bars, key=lambda b: b.get_height())
        _bubble(ax, (bmax.get_x()+bmax.get_width()/2, bmax.get_height()),
                "Mira: barra más alta = mejor", (0.05, 0.95), color="#CDEEDC")
        _bubble(ax, (bmin.get_x()+bmin.get_width()/2, bmin.get_height()),
                "Barra chiquita = más bajo", (0.6, 0.15), color="#FFE8C7")
    fig.tight_layout(); return fig

def chart_pie(g_series, theme="light", simple=False):
    if g_series.empty:
        fig, ax = plt.subplots(); return fig
        
    colors = THEMES.get(theme, THEMES["light"])
    fig = plt.figure(figsize=(10,8), facecolor=_to_rgb01(colors["bg"])); ax = fig.add_subplot(111) 
    ax.set_facecolor(_to_rgb01(colors["bg"]))
    
    if g_series.sum() > 0:
        perc = g_series / g_series.sum()
        small_slices = perc[(perc < 0.03) | (perc.rank(ascending=False) > 7)] 
        if not small_slices.empty:
            main_slices = g_series.drop(small_slices.index)
            otros_sum = g_series[small_slices.index].sum()
            if not main_slices.empty:
                g_series = pd.concat([main_slices, pd.Series([otros_sum], index=['Otros'])])
    
    vals = g_series.values; labels = g_series.index.astype(str)

    wedges, texts, autotexts = ax.pie(vals, 
                                      autopct=lambda p: f"{p:.1f}%" if p > 3 else '', 
                                      textprops={'color': _to_rgb01(colors["fg"])},
                                      pctdistance=0.85, 
                                      wedgeprops={'linewidth':1,'edgecolor':_to_rgb01(colors["bg"])})
    
    for t in autotexts: 
        t.set_color(_to_rgb01(colors["bg"]) if theme == "light" else _to_rgb01(colors["fg"]))
        t.set_fontsize(9); 
        t.set_fontweight("bold")

    ax.axis('equal')
    
    ax.legend(wedges, labels,
              title="Categorías",
              loc="center left",
              bbox_to_anchor=(0.9, 0, 0.5, 1), 
              fontsize=10)
    
    if simple and len(vals)>0:
        _bubble(ax, (0,0), "Pedazo más grande = más parte del pastel", (0.5, 0.5), color="#DDEBFF", textcoords="data")

    fig.tight_layout(rect=[0, 0, 0.75, 1]);
    return fig

def chart_line(df, x_col, y_col, theme="light", simple=False):
    colors = THEMES.get(theme, THEMES["light"])
    fig = plt.figure(figsize=(10,6), facecolor=_to_rgb01(colors["bg"])); ax = fig.add_subplot(111)
    ax.set_facecolor(_to_rgb01(colors["bg"]))
    x = _ensure_num(df[x_col]); y = _ensure_num(df[y_col])
    m = pd.DataFrame({x_col:x, y_col:y}).dropna().groupby(x_col)[y_col].mean().reset_index()
    
    if m.empty: return fig

    ax.plot(m[x_col], m[y_col], marker="o", linewidth=3, color=_to_rgb01(colors["accent"]))
    ax.set_xlabel(x_col, color=_to_rgb01(colors["fg"])); ax.set_ylabel(y_col, color=_to_rgb01(colors["fg"]))
    ax.tick_params(colors=_to_rgb01(colors["fg"]), labelsize=10)
    ax.spines['bottom'].set_color(_to_rgb01(colors["muted"])); ax.spines['left'].set_color(_to_rgb01(colors["muted"]))
    if simple and len(m)>2:
        i_max = m[y_col].idxmax(); i_min = m[y_col].idxmin()
        _bubble(ax, (m.loc[i_max,x_col], m.loc[i_max,y_col]), "Punto más alto (mejor)", (0.1, 0.8), color="#FFF0B3")
        _bubble(ax, (m.loc[i_min,x_col], m.loc[i_min,y_col]), "Punto más bajo", (0.5, 0.2), color="#FFD7E6")
    fig.tight_layout(); return fig

def chart_heatmap(df, row_col, col_col, metric_col, theme="light", simple=False):
    colors = THEMES.get(theme, THEMES["light"])
    try:
        # --- ¡INICIO CORRECCIÓN HEATMAP (image_a61db9.jpg)! ---
        # 1. Rellena con NaN (invisible) en lugar de 0.0 (morado)
        pivot = (df[[row_col, col_col, metric_col]]
                 .assign(**{metric_col: _ensure_num(df[metric_col])})
                 .dropna()
                 .groupby([row_col, col_col])[metric_col].mean()
                 .unstack(col_col).fillna(np.nan)) # <--- CORREGIDO
    except Exception:
        fig, ax = plt.subplots(); return fig

    if pivot.empty: 
        fig, ax = plt.subplots(); return fig
        
    fig = plt.figure(figsize=(12,8), facecolor=_to_rgb01(colors["bg"])); ax = fig.add_subplot(111)
    ax.set_facecolor(_to_rgb01(colors["bg"]))
    
    # 2. Copia el colormap y le dice que pinte los NaN (vacíos)
    #    con el mismo color del fondo, haciéndolos invisibles.
    my_cmap = copy.copy(plt.get_cmap('viridis'))
    my_cmap.set_bad(color=_to_rgb01(colors["bg"]))
    
    im = ax.imshow(pivot.values, aspect="auto", cmap=my_cmap)
    
    LABEL_LIMIT = 40 
    n_rows, n_cols = pivot.shape
    
    if n_cols <= LABEL_LIMIT:
        ax.set_xticks(range(n_cols))
        ax.set_xticklabels(pivot.columns.astype(str), rotation=45, ha="right", color=_to_rgb01(colors["fg"]), fontsize=9)
    else:
        ax.set_xticks([])
        ax.set_xticklabels([])
        fig.text(0.5, 0.02, f"Etiquetas del Eje X ocultas ({n_cols} > {LABEL_LIMIT})", 
                 ha='center', fontsize=9, style='italic', color=_to_rgb01(colors["muted"]))

    if n_rows <= LABEL_LIMIT:
        ax.set_yticks(range(n_rows))
        ax.set_yticklabels(pivot.index.astype(str), color=_to_rgb01(colors["fg"]), fontsize=9)
    else:
        ax.set_yticks([])
        ax.set_yticklabels([])
        fig.text(0.02, 0.5, f"Etiquetas Eje Y ocultas ({n_rows} > {LABEL_LIMIT})", 
                 va='center', rotation='vertical', fontsize=9, style='italic', color=_to_rgb01(colors["muted"]))
    
    ax.spines[:].set_visible(False)
    
    font_size = max(4, 10 - max(0, n_rows - 10) // 2)
    if n_rows < 30 and n_cols < 30:
        for i in range(n_rows):
            for j in range(n_cols):
                val = pivot.values[i,j]
                if pd.notna(val): # Solo dibuja texto si NO es NaN
                    text_color = "black" if val > np.nanmean(pivot.values) else "white"
                    ax.text(j, i, f"{val:.2f}", ha="center", va="center", color=text_color, fontsize=font_size, fontweight="bold")
    
    # --- 3. CORRECCIÓN BURBUJAS (No más "alucinaciones") ---
    if simple:
        try:
            # Encuentra min/max real, ignorando los NaN
            max_val = np.nanmax(pivot.values)
            min_val = np.nanmin(pivot.values)
            
            # Encuentra sus coordenadas (y, x)
            max_coords = np.unravel_index(np.nanargmax(pivot.values), pivot.shape)
            min_coords = np.unravel_index(np.nanargmin(pivot.values), pivot.shape)
            
            max_y, max_x = max_coords
            min_y, min_x = min_coords
            
            # Apunta la burbuja al dato MÁXIMO real
            _bubble(ax, (max_x, max_y), f"Más clarito = más alto\n(Valor: {max_val:.2f})", 
                    (0.3, 0.1), color="#EAF6FF")
            
            # Apunta la burbuja al dato MÍNIMO real (si es diferente)
            if max_val != min_val:
                _bubble(ax, (min_x, min_y), f"Más oscuro = más bajo\n(Valor: {min_val:.2f})", 
                        (0.6, 0.8), color="#FFE6EE")
        except Exception as e:
            # Fallback si todos los valores son NaN (tabla vacía)
            print(f"Error en burbuja de heatmap: {e}")
            _bubble(ax, (0,0), "No se pudieron calcular burbujas", (0.3, 0.1), color="#EAF6FF")
    # --- FIN CORRECCIÓN HEATMAP ---
            
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04); cbar.set_label("Valor medio", rotation=90)
    
    fig.tight_layout(rect=[0.05, 0.05, 1, 1]); 
    return fig

def chart_violin(df, group_col, metric_col, theme="light", simple=False, top_n=8):
    colors = THEMES.get(theme, THEMES["light"])
    fig = plt.figure(figsize=(10,6), facecolor=_to_rgb01(colors["bg"])); ax = fig.add_subplot(111)
    ax.set_facecolor(_to_rgb01(colors["bg"]))
    
    top_n_int = int(top_n)
    means = _agg_topn(df, group_col, metric_col, top_n=top_n_int) 
    
    df_plot = df[df[group_col].isin(means.index)].copy()
    df_plot[metric_col] = _ensure_num(df_plot[metric_col]).dropna()

    if df_plot.empty or len(means.index) == 0:
        fig, ax = plt.subplots(); return fig

    data_to_plot = [df_plot[df_plot[group_col] == g][metric_col].values for g in means.index]

    vp = ax.violinplot(data_to_plot, showmeans=False, showmedians=True, showextrema=False)
    for i, b in enumerate(vp['bodies']): 
        b.set_facecolor(_to_rgb01(colors["accent"])); b.set_alpha(0.85)
    vp['cmedians'].set_color('k')

    ax.set_xticks(range(1, len(means.index)+1)); 
    ax.set_xticklabels(means.index.astype(str), rotation=45, ha="right", color=_to_rgb01(colors["fg"]), fontsize=9)
    
    ax.set_ylabel(metric_col, color=_to_rgb01(colors["fg"]))
    ax.tick_params(axis='y', colors=_to_rgb01(colors["fg"]))
    
    if simple and len(data_to_plot)>0 and len(data_to_plot[0]) > 0:
        _bubble(ax, (1, float(np.median(data_to_plot[0]))), "Bolsita gordita arriba: muchos aprueban", (0.1, 0.9), color="#DFFFE2")
        if len(data_to_plot) > 1 and len(data_to_plot[-1]) > 0:
             _bubble(ax, (len(data_to_plot), float(np.median(data_to_plot[-1]))), "Punta abajo: más bajitos", (0.7, 0.1), color="#FFEBD1")
    
    fig.tight_layout(); return fig

def chart_montana(df, metric_col, theme="light", simple=False):
    colors = THEMES.get(theme, THEMES["light"])
    vals = _ensure_num(df[metric_col]).dropna().values
    
    fig, ax1 = plt.subplots(figsize=(10,6), facecolor=_to_rgb01(colors["bg"]))
    ax1.set_facecolor(_to_rgb01(colors["bg"]))
    
    if len(vals) < 10:
        ax1.text(0.5,0.5,"Muy pocos datos para Montaña", ha="center", color=_to_rgb01(colors["fg"]));
        return fig
        
    try:
        xs = np.linspace(vals.min(), vals.max(), 200)
        kde = gaussian_kde(vals); ys = kde(xs)
    except Exception:
        ax1.text(0.5,0.5,"Datos insuficientes para curva (valor único)", ha="center", color=_to_rgb01(colors["fg"]))
        return fig
        
    ecdf_x = np.sort(vals); ecdf_y = np.arange(1, len(vals)+1)/len(vals)
    
    ax1.fill_between(xs, ys, alpha=0.35, step='pre', color=_to_rgb01(colors["accent"]))
    ax1.plot(xs, ys, linewidth=3, label="Montón de estudiantes", color=_to_rgb01(colors["accent"]))
    ax1.set_ylabel("¿Cuánta gente hay? (altura del montón)", color=_to_rgb01(colors["fg"]))
    ax1.tick_params(axis='y', colors=_to_rgb01(colors["accent"]))
    ax1.tick_params(axis='x', colors=_to_rgb01(colors["fg"]))
    ax1.spines['bottom'].set_color(_to_rgb01(colors["muted"])); ax1.spines['left'].set_color(_to_rgb01(colors["muted"]))

    ax2 = ax1.twinx()
    ax2.plot(ecdf_x, ecdf_y, color="orange", linewidth=3, label="% que ya pasamos")
    ax2.set_ylabel("% acumulado", color="orange")
    ax2.tick_params(axis='y', colors="orange")
    ax2.spines['right'].set_color("orange"); 
    ax2.spines['left'].set_visible(False)
    ax2.spines['top'].set_visible(False)
    ax2.spines['bottom'].set_visible(False)
    
    ax1.legend(loc="upper left"); ax2.legend(loc="lower right")
    med = np.median(vals)
    ax1.axvline(med, linestyle="--", color="k"); 
    ax1.text(med, ax1.get_ylim()[1]*0.9, f"Mediana ≈ {med:.2f}", rotation=90, color=_to_rgb01(colors["fg"]))
    
    if simple:
        _bubble(ax1, (med, max(ys)*0.8), "Esta línea es la mitad (50%)", (0.1, 0.9), color="#E6F4FF")
        p90 = np.percentile(vals,90)
        _bubble(ax2, (p90, 0.9), "Aquí están los mejores 10%", (0.7, 0.4), color="#EAFBEA")
    
    fig.tight_layout(); return fig

def make_infographic_from_chart(fig, title, subtitle, footer, theme="light",
                                out_path="./output_images/templ_01.png"):
    canvas, draw, colors = _canvas(theme=theme)
    _draw_header(draw, colors, title, subtitle)
    _draw_footer(draw, colors, footer)
    _paste_plot_on_canvas(fig, canvas, bbox=(80, 180, 1520, 820), dpi=100) # dpi=100 para velocidad
    canvas.save(out_path, format="PNG")
    return out_path