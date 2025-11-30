import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest

def read_csv_smart(file_obj, nrows=None):
    """
    Lee un objeto de archivo (stream) en lugar de un 'path'.
    Esto soluciona el error [Errno 2] No such file or directory.
    """
    for enc in ["utf-8", "latin1", "ISO-8859-1"]:
        try:
            file_obj.seek(0) 
            return pd.read_csv(file_obj, nrows=nrows, encoding=enc)
        except Exception:
            pass
    
    file_obj.seek(0)
    return pd.read_csv(file_obj, nrows=nrows)

def summary_table(df: pd.DataFrame):
    rows = []
    for c in df.columns:
        s = df[c]
        rows.append([
            c, str(s.dtype),
            int(s.isna().sum()),
            int(s.nunique(dropna=True)),
            ", ".join(s.dropna().astype(str).head(3).tolist())
        ])
    return pd.DataFrame(rows, columns=["columna","dtype","n_miss","n_unique","muestra_valores"])

def infer_rate(df: pd.DataFrame):
    if {"cursosaprobados","cursosmatriculados"}.issubset(df.columns):
        a = pd.to_numeric(df["cursosaprobados"], errors="coerce")
        b = pd.to_numeric(df["cursosmatriculados"], errors="coerce")
        with np.errstate(divide="ignore", invalid="ignore"):
            tasa = np.where(b>0, a/b, np.nan)
        return pd.Series(tasa, index=df.index, name="__tasa__")
    return None

def valid_numeric_cols(df: pd.DataFrame):
    num = set(df.select_dtypes(include=["number","float","int"]).columns.tolist())
    for c in df.columns:
        if c not in num:
            try:
                pd.to_numeric(df[c], errors="raise")
                num.add(c)
            except Exception:
                pass
    return sorted(num)

def group_candidates(df: pd.DataFrame):
    cats = df.select_dtypes(exclude=["number","float","int"]).columns.tolist()
    low_card_nums = [
        c for c in df.select_dtypes(include=["number","float","int"]).columns
        if df[c].nunique(dropna=True) <= 20
    ]
    return list(dict.fromkeys(cats + low_card_nums))

def detect_group_anomalies(df, group_col, metric_col, method="iqr",
                           k_iqr=1.5, z_thr=2.5, mad_thr=3.5, min_n=30):
    g = df.copy()
    if group_col not in g.columns:
        return pd.DataFrame(columns=[group_col,"n","mean","anomalia"])
    
    g = g.dropna(subset=[group_col]).copy()

    if metric_col == "__tasa__":
        tasa = infer_rate(g)
        if tasa is None:
            return pd.DataFrame(columns=[group_col,"n","mean","anomalia"])
        g = g.assign(__tasa__=tasa)
        metric_col = "__tasa__"

    g[metric_col] = pd.to_numeric(g[metric_col], errors="coerce")
    g = g.dropna(subset=[metric_col])
    if g.empty:
        return pd.DataFrame(columns=[group_col,"n","mean","anomalia"])

    agg = g.groupby(group_col).agg(n=(metric_col,"count"),
                                  mean=(metric_col,"mean")).reset_index()
    agg["anomalia"] = ""
    mask = agg["n"] >= int(min_n)
    s = agg.loc[mask, "mean"].dropna()

    if len(s) < 4 or s.nunique() < 2:
        return agg.sort_values("mean", ascending=False).reset_index(drop=True)

    if method == "iqr":
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        low, high = q1 - k_iqr*iqr, q3 + k_iqr*iqr
        flags = (agg["mean"]<low) | (agg["mean"]>high)
    elif method == "z":
        m, sd = s.mean(), s.std(ddof=1)
        flags = np.abs((agg["mean"]-m)/sd) > z_thr
    else: # mad
        med = s.median()
        mad = (np.abs(s - med)).median()
        if mad <= 1e-9:
            return agg.sort_values("mean", ascending=False).reset_index(drop=True)
        z_mad = 0.6745 * (agg["mean"] - med) / mad
        flags = np.abs(z_mad) > mad_thr

    agg.loc[mask & flags, "anomalia"] = "⚠"
    return agg.sort_values("mean", ascending=False).reset_index(drop=True)

def detect_row_anomalies(df, frac=0.02, random_state=42):
    num_cols = valid_numeric_cols(df)
    if not num_cols:
        return pd.DataFrame(columns=["_score","_is_outlier"])

    # --- INICIO DE LA CORRECCIÓN PARA EL ERROR DE NaN ---
    X = df[num_cols].apply(pd.to_numeric, errors="coerce")
    
    # Rellena NaN con la mediana de cada columna
    # Esto es más robusto que ffill/bfill
    X = X.fillna(X.median())
    
    # Si alguna columna entera era NaN, su mediana también será NaN.
    # Rellenamos esos NaN restantes con 0 para asegurar que no haya ninguno.
    X = X.fillna(0)
    # --- FIN DE LA CORRECCIÓN ---

    if X.empty:
        return pd.DataFrame(columns=["_score","_is_outlier"])
        
    iso = IsolationForest(contamination=float(frac), random_state=random_state)
    scores = iso.fit_predict(X)
    dec = iso.decision_function(X)
    out = df.copy()
    out["_score"] = dec
    out["_is_outlier"] = (scores == -1).astype(int)
    return out.sort_values("_score").head(max(10, int(len(df)*frac))).reset_index(drop=True)