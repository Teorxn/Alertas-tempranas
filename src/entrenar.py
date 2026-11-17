"""Entrena y compara modelos de alerta temprana en cada momento del semestre.

Salidas:
  models/<momento>.joblib      mejor modelo + umbral + valores de referencia
  reports/metricas.csv         métricas de todos los modelos (validación cruzada y prueba)
  reports/equidad.csv          auditoría de equidad del mejor modelo por grupo
  reports/figuras/*.png        gráficas para el informe
"""
import json

import joblib
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (ConfusionMatrixDisplay, average_precision_score, f1_score,
                             fbeta_score, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold, cross_val_predict
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from config import (DATA_PATH, FIGURES_DIR, ID_COL, MODELS_DIR, MOMENTOS, NOTA_APROBATORIA,
                    REPORTS_DIR, SEMILLA, TARGET, VARIABLES_SENSIBLES)
from features import construir_features, tipos_columnas


def _preprocesador(numericas, categoricas, escalar):
    num = [SimpleImputer(strategy="median", add_indicator=True)] + ([StandardScaler()] if escalar else [])
    return ColumnTransformer([
        ("num", make_pipeline(*num), numericas),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categoricas),
    ])


def construir_modelos(numericas, categoricas):
    def pipe(clf, escalar=False):
        return Pipeline([("prep", _preprocesador(numericas, categoricas, escalar)), ("clf", clf)])

    return {
        "Regresion Logistica": pipe(LogisticRegression(class_weight="balanced", max_iter=2000), escalar=True),
        "Arbol de Decision": pipe(DecisionTreeClassifier(max_depth=5, min_samples_leaf=20,
                                                         class_weight="balanced", random_state=SEMILLA)),
        "Random Forest": pipe(RandomForestClassifier(n_estimators=300, min_samples_leaf=5, class_weight="balanced",
                                                     n_jobs=-1, random_state=SEMILLA)),
        "Gradient Boosting": pipe(HistGradientBoostingClassifier(learning_rate=0.05, max_iter=300, max_leaf_nodes=15,
                                                                 class_weight="balanced", random_state=SEMILLA)),
    }


def regla_docente(df, momento):
    """Línea base: lo que haría un profesor 'a ojo'. El modelo debe superarla."""
    if momento == "T0_inicio":
        return ((df["promedio_acumulado"] < 3.3) | (df["materias_perdidas_previas"] >= 2)).astype(float).values
    if momento == "T1_corte1":
        return (df["nota_corte1"] < NOTA_APROBATORIA).astype(float).values
    return (((df["nota_corte1"] + df["nota_corte2"]) / 2) < NOTA_APROBATORIA).astype(float).values


def metricas(y, prob, umbral):
    pred = (prob >= umbral).astype(int)
    return {
        "recall": recall_score(y, pred), "precision": precision_score(y, pred, zero_division=0),
        "f1": f1_score(y, pred), "f2": fbeta_score(y, pred, beta=2),
        "roc_auc": roc_auc_score(y, prob), "pr_auc": average_precision_score(y, prob),
        "pct_alertados": pred.mean(),
    }


def mejor_umbral_f2(y, prob):
    """Prioriza encontrar a quienes van a perder (recall) sin alertar a todo el curso."""
    candidatos = np.arange(0.10, 0.91, 0.01)
    return float(max(candidatos, key=lambda u: fbeta_score(y, (prob >= u).astype(int), beta=2)))


def valores_referencia(X):
    """Valor 'típico' de cada variable; se usa para explicar predicciones individuales."""
    return {c: (X[c].mode()[0] if X[c].dtype == object else float(X[c].median())) for c in X.columns}


def auditar_equidad(df_test, y, prob, umbral, momento):
    filas = []
    pred = prob >= umbral
    for var in VARIABLES_SENSIBLES + ["estrato", "jornada"]:
        for grupo, idx in df_test.groupby(var).groups.items():
            m = df_test.index.get_indexer(idx)
            yy, pp = y[m], pred[m]
            filas.append({
                "momento": momento, "variable": var, "grupo": grupo, "n": len(m),
                "tasa_real_perdida": yy.mean(),
                "recall": pp[yy == 1].mean() if (yy == 1).any() else np.nan,
                "tasa_falsas_alarmas": pp[yy == 0].mean() if (yy == 0).any() else np.nan,
            })
    return filas


def main():
    for d in (MODELS_DIR, FIGURES_DIR):
        d.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA_PATH)
    y_all = df[TARGET].values
    grupos = df[ID_COL].values

    # Separación por ESTUDIANTE: el mismo estudiante no puede estar en train y en test
    idx_train, idx_test = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEMILLA)
                               .split(df, y_all, grupos))
    df_train, df_test = df.iloc[idx_train].reset_index(drop=True), df.iloc[idx_test].reset_index(drop=True)
    y_train, y_test = y_all[idx_train], y_all[idx_test]
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEMILLA)
    print(f"Entrenamiento: {len(df_train)} filas | Prueba: {len(df_test)} filas | "
          f"Tasa de pérdida: {y_all.mean():.1%}\n")

    resultados, equidad, resumen = [], [], {}
    for momento in MOMENTOS:
        X_train, X_test = construir_features(df_train, momento), construir_features(df_test, momento)
        numericas, categoricas = tipos_columnas(X_train)

        base_train, base_test = regla_docente(df_train, momento), regla_docente(df_test, momento)
        resultados.append({"momento": momento, "modelo": "Regla docente (linea base)", "conjunto": "cv",
                           "umbral": 0.5, **metricas(y_train, base_train, 0.5)})
        resultados.append({"momento": momento, "modelo": "Regla docente (linea base)", "conjunto": "prueba",
                           "umbral": 0.5, **metricas(y_test, base_test, 0.5)})

        candidatos = {}
        for nombre, modelo in construir_modelos(numericas, categoricas).items():
            prob_cv = cross_val_predict(modelo, X_train, y_train, groups=df_train[ID_COL], cv=cv,
                                        method="predict_proba")[:, 1]
            umbral = mejor_umbral_f2(y_train, prob_cv)
            modelo.fit(X_train, y_train)
            prob_test = modelo.predict_proba(X_test)[:, 1]
            m_cv, m_test = metricas(y_train, prob_cv, umbral), metricas(y_test, prob_test, umbral)
            resultados.append({"momento": momento, "modelo": nombre, "conjunto": "cv", "umbral": umbral, **m_cv})
            resultados.append({"momento": momento, "modelo": nombre, "conjunto": "prueba", "umbral": umbral, **m_test})
            candidatos[nombre] = (m_cv["pr_auc"], modelo, umbral, prob_test)

        # El ganador se elige con validación cruzada (nunca mirando el conjunto de prueba)
        ganador = max(candidatos, key=lambda k: candidatos[k][0])
        _, modelo, umbral, prob_test = candidatos[ganador]
        joblib.dump({"momento": momento, "nombre": ganador, "modelo": modelo, "umbral": umbral,
                     "features": list(X_train.columns), "referencia": valores_referencia(X_train)},
                    MODELS_DIR / f"{momento}.joblib")
        equidad += auditar_equidad(df_test, y_test, prob_test, umbral, momento)
        resumen[momento] = {"modelo": ganador, "umbral": round(umbral, 2),
                            **{k: round(v, 3) for k, v in metricas(y_test, prob_test, umbral).items()}}

        _figura_importancia(modelo, X_test, y_test, momento, ganador)
        _figura_confusion(y_test, prob_test, umbral, momento, ganador)

    res = pd.DataFrame(resultados)
    res.to_csv(REPORTS_DIR / "metricas.csv", index=False, float_format="%.3f")
    pd.DataFrame(equidad).to_csv(REPORTS_DIR / "equidad.csv", index=False, float_format="%.3f")
    (REPORTS_DIR / "resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    pd.Series(df_test[ID_COL].unique()).to_csv(MODELS_DIR / "ids_prueba.csv", index=False, header=["estudiante_id"])
    _figura_comparativa(res)

    cols = ["momento", "modelo", "recall", "precision", "f2", "pr_auc", "roc_auc", "pct_alertados"]
    print(res[res["conjunto"] == "prueba"][cols].to_string(index=False, float_format="%.3f"))
    print("\nMejor modelo por momento (elegido por PR-AUC en validación cruzada):")
    for momento, r in resumen.items():
        print(f"  {momento}: {r['modelo']} | recall={r['recall']:.2f} precision={r['precision']:.2f} "
              f"PR-AUC={r['pr_auc']:.2f}")


def _figura_comparativa(res):
    prueba = res[res["conjunto"] == "prueba"]
    fig, ejes = plt.subplots(1, 2, figsize=(12, 4.5))
    for eje, metrica, titulo in ((ejes[0], "recall", "Recall (estudiantes que pierden y fueron detectados)"),
                                 (ejes[1], "pr_auc", "PR-AUC (calidad del ranking de riesgo)")):
        tabla = prueba.pivot(index="momento", columns="modelo", values=metrica).loc[list(MOMENTOS)]
        tabla.plot(kind="bar", ax=eje, rot=0, width=0.8)
        eje.set_title(titulo, fontsize=10)
        eje.set_ylim(0, 1)
        eje.set_xlabel("")
        eje.legend(fontsize=7, loc="lower right")
        eje.grid(axis="y", alpha=0.3)
    fig.suptitle("Comparación de modelos por momento del semestre (conjunto de prueba)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "comparacion_modelos.png", dpi=150)
    plt.close(fig)


def _figura_importancia(modelo, X_test, y_test, momento, nombre):
    imp = permutation_importance(modelo, X_test, y_test, scoring="average_precision",
                                 n_repeats=5, random_state=SEMILLA, n_jobs=-1)
    serie = pd.Series(imp.importances_mean, index=X_test.columns).sort_values().tail(12)
    fig, eje = plt.subplots(figsize=(7, 4.5))
    serie.plot(kind="barh", ax=eje, color="#2a6f97")
    eje.set_title(f"Variables más influyentes - {momento} ({nombre})", fontsize=10)
    eje.set_xlabel("Caída en PR-AUC al permutar la variable")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / f"importancia_{momento}.png", dpi=150)
    plt.close(fig)


def _figura_confusion(y, prob, umbral, momento, nombre):
    fig, eje = plt.subplots(figsize=(4.5, 4))
    ConfusionMatrixDisplay.from_predictions(y, (prob >= umbral).astype(int), display_labels=["Aprueba", "Pierde"],
                                            cmap="Blues", ax=eje, colorbar=False)
    eje.set_title(f"{momento} - {nombre}\numbral={umbral:.2f}", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / f"confusion_{momento}.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
