"""
Subsistema de explicación básica (XAI ligero).

Centraliza los textos asociados a cada identificador de regla del dominio (R1–R22)
y de cada regla difusa etiquetada (DF01–DF25), además de utilidades para leer
los grados de disparo Mamdani desde la simulación de scikit-fuzzy.
"""

from __future__ import annotations

from skfuzzy import control as ctrl

# Umbral mínimo de pertenencia agregada del antecedente para considerar que la
# regla difusa «aportó» de forma visible a la conclusión (evita ruido numérico).
UMBRAL_DISPARO_DIFUSO: float = 0.008

# --- Textos largos: permiten responder «¿por qué?» sin depender solo del código ---

MAPEO_DOMINIO: dict[str, str] = {
    "R1": (
        "La información del caso está incompleta o marcada como no confiable. "
        "El sistema no infiere riesgo quirúrgico hasta contar con datos suficientes."
    ),
    "R2": (
        "El paciente es menor de 18 años. La evaluación automatizada del TP está "
        "acotada a adultos; no corresponde emitir aptitud preliminar aquí."
    ),
    "R3": (
        "Existe enfermedad o condición médica no controlada. Esto incrementa el "
        "riesgo perioperatorio y debe resolverse antes de considerar cirugía electiva."
    ),
    "R4": (
        "Se registró consumo activo de drogas. Es un factor de exclusión inmediata "
        "hasta valoración especializada y eventual estabilización."
    ),
    "R5": (
        "El estado psicológico se clasifica como inestable. No es adecuado avanzar "
        "sin intervención psicológica previa."
    ),
    "R6": (
        "Las expectativas sobre el resultado son irreales respecto a lo alcanzable "
        "quirúrgicamente; se requiere alineación con el equipo tratante."
    ),
    "R7": (
        "El estado general de salud autopercibido es muy bajo (escala 1–10). "
        "Debe optimizarse antes de plantear procedimientos electivos."
    ),
    "R8": "Tabaquismo activo: incrementa complicaciones y retrasa la cicatrización.",
    "R9": "IMC en rango de sobrepeso (25–29.9): factor de riesgo moderado documentado.",
    "R10": "IMC muy elevado (≥35): riesgo metabórico y anestésico mayor.",
    "R11": "Estabilidad del peso poco favorable (escala intermedia 4–7).",
    "R12": "Estabilidad del peso inestable (escala alta ≥8): peor pronóstico en cirugía corporal.",
    "R13": "Antecedentes quirúrgicos con complicaciones previas.",
    "R14": "Cicatrización autopercibida deficiente (umbral clínico heurístico ≥6 en escala 1–10).",
    "R15": "Estado psicológico dudoso: requiere clarificación o apoyo antes de decisión firme.",
    "R16": "Expectativas poco claras: conviene entrevista médica detallada.",
    "R17": "Abdominoplastía (o combinada) con peso inestable: riesgo de resultados y complicaciones.",
    "R18": "Abdominoplastía (o combinada) con cicatrización mala: alerta técnica.",
    "R19": (
        "Perfil favorable para liposucción según criterios documentados "
        "(salud alta, IMC acotado, expectativas realistas y riesgo difuso bajo)."
    ),
    "R20": "Deseo de ambos procedimientos con varios factores moderados acumulados.",
    "R21": "Conteo de factores de riesgo moderado ≥2: se fuerza al menos riesgo medio numérico.",
    "R22": "Conteo de factores de riesgo moderado ≥3: se fuerza al menos riesgo alto numérico.",
}

# Descripciones alineadas con el orden de construcción en main._construir_sistema_difuso
MAPEO_DIFUSO: dict[str, str] = {
    "DF01": (
        "Perfil corporal y de hábitos favorable: IMC normal, salud buena, peso estable, "
        "expectativas realistas, edad joven o adulta, sin tabaco ni antecedentes graves."
    ),
    "DF02": "IMC bajo (delgadez relativa): al menos riesgo intermedio por reservas nutricionales.",
    "DF03": "IMC moderadamente elevado: riesgo intermedio en meseta de salida.",
    "DF04": "IMC elevado: empuja el consecuente hacia riesgo alto.",
    "DF05": "IMC muy elevado: riesgo alto en la base difusa.",
    "DF06": "Inestabilidad moderada del peso: contribución a riesgo medio.",
    "DF07": "Inestabilidad marcada del peso: contribución a riesgo alto.",
    "DF08": "Estado general de salud solo regular (no óptimo): riesgo medio.",
    "DF09": "Expectativas poco claras en escala difusa: riesgo medio.",
    "DF10": "Edad adulta mayor con salud buena e IMC normal: aún así riesgo no trivial (medio).",
    "DF11": "Edad adulta mayor con IMC elevado o moderadamente elevado: riesgo alto.",
    "DF12": "Edad adulta mayor con salud regular: riesgo alto.",
    "DF13": "Tabaquismo activo (antecedente binario difusificado): incrementa riesgo al menos a medio.",
    "DF14": "Tabaquismo combinado con IMC elevado o muy elevado: refuerzo hacia riesgo alto.",
    "DF15": "Tabaquismo con inestabilidad de peso: patrón de riesgo alto.",
    "DF16": "Cirugías previas con complicaciones: riesgo al menos medio.",
    "DF17": "Complicaciones quirúrgicas previas más IMC elevado: riesgo alto.",
    "DF18": "Cicatrización mala declarada: riesgo al menos medio.",
    "DF19": "Cicatrización mala con peso inestable: riesgo alto.",
    "DF20": "Abdominoplastía (antecedente) con peso inestable: riesgo alto.",
    "DF21": "Abdominoplastía (antecedente) con cicatrización mala: riesgo alto.",
    "DF22": "Salud regular y expectativas poco claras conjuntamente: refuerzo a riesgo medio.",
    "DF23": "Tabaquismo, peso poco estable y salud regular: triple moderado → riesgo alto.",
    "DF24": "IMC moderadamente elevado, peso poco estable y tabaquismo: riesgo alto.",
    "DF25": "Complicaciones quirúrgicas previas y cicatrización mala: riesgo alto acumulado.",
}


def descripcion_dominio(codigo: str) -> str:
    """Devuelve el texto explicativo de una regla de dominio conocida o un mensaje genérico."""
    return MAPEO_DOMINIO.get(codigo, f"Regla de dominio {codigo} (sin descripción extendida).")


def descripcion_difusa(codigo: str) -> str:
    """Devuelve el texto explicativo de una regla difusa etiquetada."""
    return MAPEO_DIFUSO.get(codigo, "Regla difusa Mamdani del motor (sin etiqueta en el mapa).")


def disparos_difusos_desde_simulacion(
    sim: ctrl.ControlSystemSimulation,
    umbral: float = UMBRAL_DISPARO_DIFUSO,
) -> list[tuple[str, float]]:
    """
    Lee, tras ``compute()``, el grado de cumplimiento del antecedente de cada regla.

    Returns
    -------
    Lista de pares (etiqueta DFxx, grado) ordenada de mayor a menor grado.
    """
    resultado: list[tuple[str, float]] = []
    for rule in sim.ctrl.rules:
        firing = rule.aggregate_firing[sim]
        if firing is None:
            continue
        grado = float(firing)
        if grado < umbral:
            continue
        etiqueta = str(rule.label)
        resultado.append((etiqueta, grado))
    resultado.sort(key=lambda par: -par[1])
    return resultado
