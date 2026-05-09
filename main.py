"""
Sistema Experto híbrido (reglas + lógica difusa) para evaluación preliminar
de aptitud/riesgo en cirugía estética corporal — según TP2 documentado.

Ejecución: uvicorn main:app --reload
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import skfuzzy as fuzz
from fastapi import FastAPI
from pydantic import BaseModel, Field
from skfuzzy import control as ctrl

# --- Constantes de dominio (literales del documento) ---

Procedimiento = Literal["abdominoplastía", "liposucción", "ambos"]
EstabilidadPeso = Literal["estable", "poco estable", "inestable"]
EstadoSalud = Literal["bueno", "regular", "malo"]
AntecedentesQx = Literal[
    "sin antecedentes",
    "cirugía previa sin complicaciones",
    "cirugía previa con complicaciones",
]
Cicatrizacion = Literal["normal", "mala"]
EstadoPsicologico = Literal["estable", "dudoso", "inestable"]
Expectativas = Literal["realistas", "poco claras", "irreales"]
Aptitud = Literal[
    "apto preliminarmente",
    "apto con condiciones",
    "no apto preliminarmente",
    "requiere mayor información",
]
NivelRiesgoCat = Literal["bajo", "medio", "alto"]


class MemoriaTrabajo(BaseModel):
    """Memoria de trabajo: hechos del paciente (entrada API)."""

    edad: int = Field(..., ge=0, le=120)
    procedimiento_deseado: Procedimiento
    imc: float = Field(..., ge=0, le=60)
    estabilidad_peso: EstabilidadPeso
    estado_general_salud: EstadoSalud
    enfermedad_no_controlada: bool
    tabaquismo: bool
    consume_drogas: bool
    antecedentes_quirurgicos: AntecedentesQx
    cicatrizacion: Cicatrizacion
    estado_psicologico: EstadoPsicologico
    expectativas: Expectativas
    informacion_completa: bool


class EvaluacionResultado(BaseModel):
    aptitud_preliminar: Aptitud
    nivel_riesgo: NivelRiesgoCat
    nivel_riesgo_numerico: float = Field(..., description="0–100 tras defuzzificación (centroide)")
    recomendacion: str
    derivacion_sugerida: str
    reglas_activadas: list[str]


app = FastAPI(
    title="Sistema Experto — Evaluación preliminar cirugía estética corporal",
    version="1.0.0",
)


def _estabilidad_a_escala(estabilidad: EstabilidadPeso) -> float:
    """Escala 0–10: 0 estable, 10 muy inestable (documento)."""
    return {"estable": 1.0, "poco estable": 5.0, "inestable": 9.0}[estabilidad]


def _salud_a_escala(salud: EstadoSalud) -> float:
    """Escala 0–10: 0 malo, 10 bueno (documento)."""
    return {"malo": 1.5, "regular": 5.0, "bueno": 9.0}[salud]


def _expectativas_a_escala(exp: Expectativas) -> float:
    """Escala 0–10: 0 irreales, 10 realistas (documento)."""
    return {"irreales": 1.5, "poco claras": 5.0, "realistas": 9.0}[exp]


def _construir_sistema_difuso() -> ctrl.ControlSystemSimulation:
    """
    Variables y funciones de membresía EXACTAS según 'Funciones de membresía propuestas'.
    Salida: Nivel de riesgo 0–100 (bajo/medio/alto).
    """
    # Universos
    edad = ctrl.Antecedent(np.arange(18, 81, 1), "edad")
    imc = ctrl.Antecedent(np.arange(0, 46, 0.25), "imc")
    estabilidad = ctrl.Antecedent(np.arange(0, 10.05, 0.05), "estabilidad")
    salud = ctrl.Antecedent(np.arange(0, 10.05, 0.05), "salud")
    expectativas = ctrl.Antecedent(np.arange(0, 10.05, 0.05), "expectativas")
    # Fase 4–5: factores moderados como antecedentes en [0, 1]
    tabaco = ctrl.Antecedent(np.arange(0, 1.01, 0.01), "tabaco")
    complicaciones_qx = ctrl.Antecedent(np.arange(0, 1.01, 0.01), "complicaciones_qx")
    cicatriz_mala = ctrl.Antecedent(np.arange(0, 1.01, 0.01), "cicatriz_mala")
    proc_abdom = ctrl.Antecedent(np.arange(0, 1.01, 0.01), "proc_abdom")

    riesgo = ctrl.Consequent(np.arange(0, 101, 1), "riesgo")

    # --- Edad (documento) ---
    edad["adulto_joven"] = fuzz.trapmf(edad.universe, [18, 18, 30, 40])
    edad["adulto"] = fuzz.trimf(edad.universe, [30, 45, 60])
    edad["adulto_mayor"] = fuzz.trapmf(edad.universe, [55, 65, 80, 80])

    # --- IMC (documento) ---
    imc["bajo"] = fuzz.trapmf(imc.universe, [0, 0, 17, 18.5])
    imc["normal"] = fuzz.trapmf(imc.universe, [18, 18.5, 24.9, 26])
    imc["moderadamente_elevado"] = fuzz.trimf(imc.universe, [25, 27.5, 30])
    imc["elevado"] = fuzz.trimf(imc.universe, [29, 32.5, 35])
    imc["muy_elevado"] = fuzz.trapmf(imc.universe, [34, 35, 45, 45])

    # --- Estabilidad del peso 0–10 (documento) ---
    estabilidad["estable"] = fuzz.trapmf(estabilidad.universe, [0, 0, 2, 4])
    estabilidad["poco_estable"] = fuzz.trimf(estabilidad.universe, [3, 5, 7])
    estabilidad["inestable"] = fuzz.trapmf(estabilidad.universe, [6, 8, 10, 10])

    # --- Estado general de salud 0–10 (documento; 0 malo, 10 bueno) ---
    salud["malo"] = fuzz.trapmf(salud.universe, [0, 0, 2, 4])
    salud["regular"] = fuzz.trimf(salud.universe, [3, 5, 7])
    salud["bueno"] = fuzz.trapmf(salud.universe, [6, 8, 10, 10])

    # --- Expectativas 0–10 (documento; 0 irreales, 10 realistas) ---
    expectativas["irreales"] = fuzz.trapmf(expectativas.universe, [0, 0, 2, 4])
    expectativas["poco_claras"] = fuzz.trimf(expectativas.universe, [3, 5, 7])
    expectativas["realistas"] = fuzz.trapmf(expectativas.universe, [6, 8, 10, 10])

    # --- Nivel de riesgo salida 0–100 (documento); defuzzificación: centroide ---
    riesgo["bajo"] = fuzz.trapmf(riesgo.universe, [0, 0, 25, 40])
    riesgo["medio"] = fuzz.trimf(riesgo.universe, [30, 50, 70])
    riesgo["alto"] = fuzz.trapmf(riesgo.universe, [60, 75, 100, 100])
    riesgo.defuzzify_method = "centroid"

    # --- Binarios difusificados en [0,1] (Fase 4–5) ---
    tabaco["no"] = fuzz.trapmf(tabaco.universe, [0, 0, 0.05, 0.45])
    tabaco["si"] = fuzz.trapmf(tabaco.universe, [0.55, 0.95, 1, 1])

    complicaciones_qx["no"] = fuzz.trapmf(complicaciones_qx.universe, [0, 0, 0.05, 0.45])
    complicaciones_qx["si"] = fuzz.trapmf(complicaciones_qx.universe, [0.55, 0.95, 1, 1])

    cicatriz_mala["no"] = fuzz.trapmf(cicatriz_mala.universe, [0, 0, 0.05, 0.45])
    cicatriz_mala["si"] = fuzz.trapmf(cicatriz_mala.universe, [0.55, 0.95, 1, 1])

    proc_abdom["no"] = fuzz.trapmf(proc_abdom.universe, [0, 0, 0.05, 0.45])
    proc_abdom["si"] = fuzz.trapmf(proc_abdom.universe, [0.55, 0.95, 1, 1])

    # ========== Reglas difusas: antecedentes → consecuente riesgo ==========
    # Fase 3–5: combinaciones que reflejan R8–R18 y tablas del dominio.
    rules: list[ctrl.Rule] = [
        # Perfil favorable (R19-like, sin factores críticos ya filtrados)
        ctrl.Rule(
            imc["normal"]
            & salud["bueno"]
            & estabilidad["estable"]
            & expectativas["realistas"]
            & (edad["adulto_joven"] | edad["adulto"])
            & tabaco["no"]
            & complicaciones_qx["no"]
            & cicatriz_mala["no"],
            riesgo["bajo"],
        ),
        # IMC bajo: requiere evaluación; riesgo al menos medio
        ctrl.Rule(imc["bajo"], riesgo["medio"]),
        ctrl.Rule(imc["moderadamente_elevado"], riesgo["medio"]),
        ctrl.Rule(imc["elevado"], riesgo["alto"]),
        ctrl.Rule(imc["muy_elevado"], riesgo["alto"]),
        # Estabilidad del peso
        ctrl.Rule(estabilidad["poco_estable"], riesgo["medio"]),
        ctrl.Rule(estabilidad["inestable"], riesgo["alto"]),
        # Salud y expectativas graduales (Fase 3); 'malo' suele cortarse en R7
        ctrl.Rule(salud["regular"], riesgo["medio"]),
        ctrl.Rule(expectativas["poco_claras"], riesgo["medio"]),
        # Edad mayor aporta más riesgo si no todo es óptimo
        ctrl.Rule(edad["adulto_mayor"] & salud["bueno"] & imc["normal"], riesgo["medio"]),
        ctrl.Rule(edad["adulto_mayor"] & (imc["moderadamente_elevado"] | imc["elevado"]), riesgo["alto"]),
        ctrl.Rule(edad["adulto_mayor"] & salud["regular"], riesgo["alto"]),
        # Tabaquismo R8
        ctrl.Rule(tabaco["si"], riesgo["medio"]),
        ctrl.Rule(tabaco["si"] & (imc["elevado"] | imc["muy_elevado"]), riesgo["alto"]),
        ctrl.Rule(tabaco["si"] & estabilidad["inestable"], riesgo["alto"]),
        # Antecedentes R13 / cicatriz R14
        ctrl.Rule(complicaciones_qx["si"], riesgo["medio"]),
        ctrl.Rule(complicaciones_qx["si"] & (imc["elevado"] | imc["muy_elevado"]), riesgo["alto"]),
        ctrl.Rule(cicatriz_mala["si"], riesgo["medio"]),
        ctrl.Rule(cicatriz_mala["si"] & estabilidad["inestable"], riesgo["alto"]),
        # Procedimiento abdominoplastía + factores corporales (R17–R18)
        ctrl.Rule(proc_abdom["si"] & estabilidad["inestable"], riesgo["alto"]),
        ctrl.Rule(proc_abdom["si"] & cicatriz_mala["si"], riesgo["alto"]),
        # Estado psicológico dudoso R15 → condiciones / riesgo medio+
        ctrl.Rule(salud["regular"] & expectativas["poco_claras"], riesgo["medio"]),
        # Acumulación de varios factores moderados (refuerzo R20–R22 vía reglas)
        ctrl.Rule(
            tabaco["si"] & estabilidad["poco_estable"] & salud["regular"],
            riesgo["alto"],
        ),
        ctrl.Rule(
            imc["moderadamente_elevado"] & estabilidad["poco_estable"] & tabaco["si"],
            riesgo["alto"],
        ),
        ctrl.Rule(complicaciones_qx["si"] & cicatriz_mala["si"], riesgo["alto"]),
    ]

    sistema = ctrl.ControlSystem(rules)
    return ctrl.ControlSystemSimulation(sistema)


_SISTEMA_CACHE: ctrl.ControlSystemSimulation | None = None


def _obtener_simulacion() -> ctrl.ControlSystemSimulation:
    global _SISTEMA_CACHE
    if _SISTEMA_CACHE is None:
        _SISTEMA_CACHE = _construir_sistema_difuso()
    return _SISTEMA_CACHE


def _riesgo_categoria_documento(valor: float) -> NivelRiesgoCat:
    """Tabla 'Método de defuzzificación': 0–35 bajo, 36–70 medio, 71–100 alto."""
    v = float(np.clip(valor, 0, 100))
    if v <= 35:
        return "bajo"
    if v <= 70:
        return "medio"
    return "alto"


def _contar_factores_moderados(mt: MemoriaTrabajo) -> int:
    """Heurística alineada con R8–R16 y R21–R22 (factores de riesgo moderado)."""
    n = 0
    if mt.tabaquismo:
        n += 1
    if mt.imc >= 25.0:
        n += 1
    if mt.estabilidad_peso in ("poco estable", "inestable"):
        n += 1
    if mt.estado_general_salud == "regular":
        n += 1
    if mt.antecedentes_quirurgicos == "cirugía previa con complicaciones":
        n += 1
    if mt.cicatrizacion == "mala":
        n += 1
    if mt.estado_psicologico == "dudoso":
        n += 1
    if mt.expectativas == "poco claras":
        n += 1
    return n


def _ajuste_r21_r22(riesgo_num: float, moderados: int) -> float:
    """R21: ≥2 moderados → riesgo medio; R22: ≥3 moderados → riesgo alto."""
    r = riesgo_num
    if moderados >= 3:
        r = max(r, 72.0)
    elif moderados >= 2:
        r = max(r, 36.0)
    return float(min(100.0, r))


def _clasificacion_aptitud_sin_criticos(
    riesgo_num: float, nivel: NivelRiesgoCat, moderados: int
) -> Aptitud:
    """
    Si no hay reglas críticas: bajo → apto preliminar; medio → apto condiciones;
    alto → apto con condiciones o no apto según combinación (R25: gravedad acumulada).
    Se reserva «no apto» para riesgo numérico muy elevado o acumulación extrema de
    factores moderados, coherente con «apto con condiciones y riesgo alto» del informe.
    """
    if nivel == "bajo":
        return "apto preliminarmente"
    if nivel == "medio":
        return "apto con condiciones"
    # alto (sin reglas críticas)
    if riesgo_num >= 88.0 or moderados >= 6:
        return "no apto preliminarmente"
    return "apto con condiciones"


def evaluar_paciente(mt: MemoriaTrabajo) -> EvaluacionResultado:
    reglas: list[str] = []
    recomendaciones: list[str] = []

    # ----- Fase 1: R1 -----
    if not mt.informacion_completa:
        reglas.append("R1")
        return EvaluacionResultado(
            aptitud_preliminar="requiere mayor información",
            nivel_riesgo="medio",
            nivel_riesgo_numerico=50.0,
            recomendacion="Los datos disponibles no son suficientes para emitir una conclusión confiable. "
            "Solicite más información antes de continuar.",
            derivacion_sugerida="ninguna",
            reglas_activadas=reglas,
        )

    # ----- Fase 2: R2–R7 (reglas críticas; prioridad inmediata) -----
    if mt.edad < 18:
        reglas.append("R2")
        return EvaluacionResultado(
            aptitud_preliminar="no apto preliminarmente",
            nivel_riesgo="alto",
            nivel_riesgo_numerico=95.0,
            recomendacion="El análisis del sistema se limita a pacientes adultos. No se recomienda avanzar "
            "con esta evaluación automatizada.",
            derivacion_sugerida="ninguna",
            reglas_activadas=reglas,
        )

    if mt.enfermedad_no_controlada:
        reglas.append("R3")
        return EvaluacionResultado(
            aptitud_preliminar="no apto preliminarmente",
            nivel_riesgo="alto",
            nivel_riesgo_numerico=90.0,
            recomendacion="Enfermedad o condición no controlada: se desaconseja avanzar sin control médico previo.",
            derivacion_sugerida="médico clínico",
            reglas_activadas=reglas,
        )

    if mt.consume_drogas:
        reglas.append("R4")
        return EvaluacionResultado(
            aptitud_preliminar="no apto preliminarmente",
            nivel_riesgo="alto",
            nivel_riesgo_numerico=95.0,
            recomendacion="Consumo de drogas: caso de alta alerta; no avanzar sin evaluación profesional.",
            derivacion_sugerida="médico clínico / psicólogo",
            reglas_activadas=reglas,
        )

    if mt.estado_psicologico == "inestable":
        reglas.append("R5")
        return EvaluacionResultado(
            aptitud_preliminar="no apto preliminarmente",
            nivel_riesgo="alto",
            nivel_riesgo_numerico=92.0,
            recomendacion="Inestabilidad psicológica relevante: se recomienda evaluación psicológica antes de continuar.",
            derivacion_sugerida="psicólogo",
            reglas_activadas=reglas,
        )

    if mt.expectativas == "irreales":
        reglas.append("R6")
        return EvaluacionResultado(
            aptitud_preliminar="no apto preliminarmente",
            nivel_riesgo="alto",
            nivel_riesgo_numerico=90.0,
            recomendacion="Expectativas irreales: no se recomienda avanzar sin orientación profesional sobre límites "
            "y resultados posibles.",
            derivacion_sugerida="psicólogo / cirujano plástico",
            reglas_activadas=reglas,
        )

    if mt.estado_general_salud == "malo":
        reglas.append("R7")
        return EvaluacionResultado(
            aptitud_preliminar="no apto preliminarmente",
            nivel_riesgo="alto",
            nivel_riesgo_numerico=93.0,
            recomendacion="Estado general de salud malo: se requiere evaluación y optimización médica previa.",
            derivacion_sugerida="médico clínico",
            reglas_activadas=reglas,
        )

    # ----- Fase 3–5: motor difuso (centroide) + reglas moderadas R21–R22 -----
    sim = _obtener_simulacion()
    sim.input["edad"] = float(mt.edad)
    sim.input["imc"] = float(mt.imc)
    sim.input["estabilidad"] = _estabilidad_a_escala(mt.estabilidad_peso)
    sim.input["salud"] = _salud_a_escala(mt.estado_general_salud)
    sim.input["expectativas"] = _expectativas_a_escala(mt.expectativas)
    sim.input["tabaco"] = 1.0 if mt.tabaquismo else 0.0
    sim.input["complicaciones_qx"] = (
        1.0 if mt.antecedentes_quirurgicos == "cirugía previa con complicaciones" else 0.0
    )
    sim.input["cicatriz_mala"] = 1.0 if mt.cicatrizacion == "mala" else 0.0
    sim.input["proc_abdom"] = (
        1.0 if mt.procedimiento_deseado in ("abdominoplastía", "ambos") else 0.0
    )

    sim.compute()
    riesgo_crisp = float(sim.output["riesgo"])

    moderados = _contar_factores_moderados(mt)
    riesgo_ajustado = _ajuste_r21_r22(riesgo_crisp, moderados)
    nivel = _riesgo_categoria_documento(riesgo_ajustado)
    aptitud = _clasificacion_aptitud_sin_criticos(riesgo_ajustado, nivel, moderados)

    # Reglas activadas (trazabilidad)
    reglas.append("Fase3-Fase5-difuso")
    if moderados >= 3:
        reglas.append("R22")
    elif moderados >= 2:
        reglas.append("R21")
    if mt.tabaquismo:
        reglas.append("R8")
    if 25 <= mt.imc < 30:
        reglas.append("R9")
    if mt.imc >= 35:
        reglas.append("R10")
    if mt.estabilidad_peso == "poco estable":
        reglas.append("R11")
    if mt.estabilidad_peso == "inestable":
        reglas.append("R12")
    if mt.antecedentes_quirurgicos == "cirugía previa con complicaciones":
        reglas.append("R13")
    if mt.cicatrizacion == "mala":
        reglas.append("R14")
    if mt.estado_psicologico == "dudoso":
        reglas.append("R15")
    if mt.expectativas == "poco claras":
        reglas.append("R16")
    if mt.procedimiento_deseado in ("abdominoplastía", "ambos") and mt.estabilidad_peso == "inestable":
        reglas.append("R17")
    if mt.procedimiento_deseado in ("abdominoplastía", "ambos") and mt.cicatrizacion == "mala":
        reglas.append("R18")
    if (
        mt.procedimiento_deseado == "liposucción"
        and mt.estado_general_salud == "bueno"
        and mt.imc <= 30
        and mt.expectativas == "realistas"
        and nivel == "bajo"
    ):
        reglas.append("R19")
    if mt.procedimiento_deseado == "ambos" and moderados >= 2:
        reglas.append("R20")

    # Recomendación textual
    if nivel == "bajo":
        recomendaciones.append(
            "Riesgo bajo según factores graduales y reglas moderadas. Puede avanzar hacia una evaluación médica formal."
        )
    elif nivel == "medio":
        recomendaciones.append(
            "Riesgo medio: suelen requerirse control de hábitos, estudios complementarios o evaluación adicional."
        )
    else:
        recomendaciones.append(
            "Riesgo alto: conviene postergar o profundizar la evaluación antes de considerar el procedimiento."
        )

    if mt.tabaquismo:
        recomendaciones.append("Suspender tabaquismo según indicación profesional previa a cirugía (R8).")
    if mt.estabilidad_peso == "inestable":
        recomendaciones.append(
            "Priorizar estabilización del peso antes de una evaluación quirúrgica, especialmente en abdominoplastía (R12/R17)."
        )
    if 25 <= mt.imc < 35:
        recomendaciones.append("IMC por encima de lo normal: se sugiere evaluación clínica o nutricional previa (R9).")
    if mt.imc >= 35:
        recomendaciones.append("IMC muy elevado: se recomienda evaluación médica antes de avanzar (R10).")
    if aptitud == "apto preliminarmente":
        recomendaciones.append("Clasificación: apto preliminarmente (sin reglas críticas y riesgo bajo).")
    elif aptitud == "apto con condiciones":
        recomendaciones.append(
            "Clasificación: apto con condiciones (puede incluirse riesgo alto sin factores críticos excluyentes)."
        )
    else:
        recomendaciones.append("Clasificación: no apto preliminarmente por combinación muy desfavorable de factores.")

    derivacion = "ninguna"
    if nivel != "bajo" or mt.imc >= 30:
        derivacion = "médico clínico / cirujano plástico"
    if mt.estado_psicologico == "dudoso":
        derivacion = "psicólogo / cirujano plástico"
    if mt.expectativas == "poco claras":
        derivacion = "cirujano plástico"

    return EvaluacionResultado(
        aptitud_preliminar=aptitud,
        nivel_riesgo=nivel,
        nivel_riesgo_numerico=round(riesgo_ajustado, 2),
        recomendacion=" ".join(recomendaciones),
        derivacion_sugerida=derivacion,
        reglas_activadas=sorted(set(reglas), key=lambda x: (x[0] != "R", x)),
    )


@app.get("/")
def raiz() -> dict[str, str]:
    """La raíz no evalúa pacientes; la prueba interactiva está en /docs."""
    return {
        "mensaje": "Sistema Experto API activa.",
        "probar_interfaz": "/docs",
        "salud": "/health",
        "evaluar": "POST /evaluar (cuerpo JSON según MemoriaTrabajo)",
    }


@app.post("/evaluar", response_model=EvaluacionResultado)
def endpoint_evaluar(memoria: MemoriaTrabajo) -> EvaluacionResultado:
    return evaluar_paciente(memoria)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
