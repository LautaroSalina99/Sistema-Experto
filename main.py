"""
Sistema Experto híbrido (reglas duras + lógica difusa) para evaluación preliminar
de aptitud/riesgo en cirugía estética corporal — según TP2 documentado.

Incluye un subsistema de explicación básico: cada respuesta expone qué reglas
participaron (dominio R1–R22, motor difuso DF01–DF25 con grado de activación) y
un texto «por qué» en ``explicacion_conclusion``.

Ejecución: ``python -m uvicorn main:app --reload`` o ``run.bat`` en Windows.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import skfuzzy as fuzz
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from skfuzzy import control as ctrl

from explicacion_reglas import (
    descripcion_difusa,
    descripcion_dominio,
    disparos_difusos_desde_simulacion,
)

# --- Constantes de dominio (literales del documento) ---

Procedimiento = Literal["abdominoplastía", "liposucción", "ambos"]
AntecedentesQx = Literal[
    "sin antecedentes",
    "cirugía previa sin complicaciones",
    "cirugía previa con complicaciones",
]
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
    """
    Memoria de trabajo: hechos del paciente tal como los ingresa la API.

    Los escalares 1–10 siguen la semántica del informe (mayor es mejor salvo
    donde se documente lo contrario, p. ej. estabilidad del peso).
    """

    edad: int = Field(..., ge=0, le=120)
    procedimiento_deseado: Procedimiento
    imc: float = Field(..., ge=0, le=60)
    estabilidad_peso: int = Field(..., ge=1, le=10)
    estado_general_salud: int = Field(..., ge=1, le=10)
    enfermedad_no_controlada: bool
    tabaquismo: bool
    consume_drogas: bool
    antecedentes_quirurgicos: AntecedentesQx
    cicatrizacion: int = Field(..., ge=1, le=10)
    estado_psicologico: EstadoPsicologico
    expectativas: Expectativas
    informacion_completa: bool


class ReglaActivada(BaseModel):
    """
    Elemento del subsistema de explicación: identifica una regla que influyó
    en la decisión y ofrece lenguaje natural para trazabilidad clínica.
    """

    codigo: str
    categoria: Literal[
        "informacion",
        "corte_prioritario",
        "difusa_mamdani",
        "trazabilidad_dominio",
        "postproceso_numerico",
    ]
    descripcion: str
    grado_activacion: float | None = Field(
        default=None,
        description="Grado de disparo Mamdani del antecedente (solo reglas difusas).",
    )


class EvaluacionResultado(BaseModel):
    aptitud_preliminar: Aptitud
    nivel_riesgo: NivelRiesgoCat
    nivel_riesgo_numerico: float = Field(..., description="0–100 tras defuzzificación (centroide)")
    recomendacion: str
    derivacion_sugerida: str
    reglas_activadas: list[str]
    reglas_explicadas: list[ReglaActivada] = Field(
        default_factory=list,
        description="Lista ordenada de reglas con texto explicativo y, si aplica, grado difuso.",
    )
    explicacion_conclusion: str = Field(
        default="",
        description="Resumen en prosa que responde: ¿por qué el sistema llegó a esta conclusión?",
    )


app = FastAPI(
    title="Sistema Experto — Evaluación preliminar cirugía estética corporal",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _es_salud_mala(valor: int) -> bool:
    """1..10 donde valores bajos representan peor estado general."""
    return valor <= 3


def _es_peso_inestable(valor: int) -> bool:
    """1..10 donde valores altos representan mayor inestabilidad."""
    return valor >= 8


def _es_peso_poco_estable(valor: int) -> bool:
    """Rango intermedio de estabilidad de peso."""
    return 4 <= valor <= 7


def _cicatrizacion_mala_factor(valor: int) -> float:
    """Mapea 1..10 (normal→mala) a factor difuso [0..1]."""
    return float(np.clip((valor - 1) / 9, 0.0, 1.0))


def _es_cicatrizacion_mala(valor: int) -> bool:
    """Umbral clínico heurístico para etiquetas/reglas discretas."""
    return valor >= 6


def _expectativas_a_escala(exp: Expectativas) -> float:
    """Escala 0–10: 0 irreales, 10 realistas (documento)."""
    return {"irreales": 1.5, "poco claras": 5.0, "realistas": 9.0}[exp]


def _construir_sistema_difuso() -> ctrl.ControlSystemSimulation:
    """
    Construye antecedentes, consecuente, funciones de membresía y la base de reglas Mamdani.

    Cada ``ctrl.Rule`` incluye ``label`` único (DF01–DF25) para enlazar con textos en
    ``explicacion_reglas`` y reportar grados de disparo tras ``compute()``.
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

    # ========== Reglas difusas Mamdani (DF01–DF25): antecedentes → riesgo ==========
    # Cada regla lleva ``label`` único para el subsistema de explicación (grados de disparo).
    rules: list[ctrl.Rule] = [
        # --- Bloque «perfil favorable»: empuja riesgo bajo si todo el conjunto encaja ---
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
            label="DF01",
        ),
        # --- Bloque IMC: clases documentadas de delgadez a obesidad severa ---
        ctrl.Rule(imc["bajo"], riesgo["medio"], label="DF02"),
        ctrl.Rule(imc["moderadamente_elevado"], riesgo["medio"], label="DF03"),
        ctrl.Rule(imc["elevado"], riesgo["alto"], label="DF04"),
        ctrl.Rule(imc["muy_elevado"], riesgo["alto"], label="DF05"),
        # --- Bloque estabilidad ponderal (escala 0–10 difusa) ---
        ctrl.Rule(estabilidad["poco_estable"], riesgo["medio"], label="DF06"),
        ctrl.Rule(estabilidad["inestable"], riesgo["alto"], label="DF07"),
        # --- Bloque salud / expectativas graduales (Fase 3); «malo» se filtra antes por R7 ---
        ctrl.Rule(salud["regular"], riesgo["medio"], label="DF08"),
        ctrl.Rule(expectativas["poco_claras"], riesgo["medio"], label="DF09"),
        # --- Bloque edad adulta mayor: refina riesgo aun con subconjuntos «buenos» ---
        ctrl.Rule(edad["adulto_mayor"] & salud["bueno"] & imc["normal"], riesgo["medio"], label="DF10"),
        ctrl.Rule(
            edad["adulto_mayor"] & (imc["moderadamente_elevado"] | imc["elevado"]),
            riesgo["alto"],
            label="DF11",
        ),
        ctrl.Rule(edad["adulto_mayor"] & salud["regular"], riesgo["alto"], label="DF12"),
        # --- Bloque tabaquismo (antecedente binario difusificado, coherente con R8) ---
        ctrl.Rule(tabaco["si"], riesgo["medio"], label="DF13"),
        ctrl.Rule(tabaco["si"] & (imc["elevado"] | imc["muy_elevado"]), riesgo["alto"], label="DF14"),
        ctrl.Rule(tabaco["si"] & estabilidad["inestable"], riesgo["alto"], label="DF15"),
        # --- Bloque antecedentes quirúrgicos y cicatrización (R13–R14 en dominio) ---
        ctrl.Rule(complicaciones_qx["si"], riesgo["medio"], label="DF16"),
        ctrl.Rule(
            complicaciones_qx["si"] & (imc["elevado"] | imc["muy_elevado"]),
            riesgo["alto"],
            label="DF17",
        ),
        ctrl.Rule(cicatriz_mala["si"], riesgo["medio"], label="DF18"),
        ctrl.Rule(cicatriz_mala["si"] & estabilidad["inestable"], riesgo["alto"], label="DF19"),
        # --- Bloque procedimiento abdominal (R17–R18) ---
        ctrl.Rule(proc_abdom["si"] & estabilidad["inestable"], riesgo["alto"], label="DF20"),
        ctrl.Rule(proc_abdom["si"] & cicatriz_mala["si"], riesgo["alto"], label="DF21"),
        # --- Bloque refuerzo salud + expectativas ambiguas (relacionado con R15–R16) ---
        ctrl.Rule(salud["regular"] & expectativas["poco_claras"], riesgo["medio"], label="DF22"),
        # --- Bloque acumulación de moderados (refuerzo numérico alineado con R20–R22) ---
        ctrl.Rule(
            tabaco["si"] & estabilidad["poco_estable"] & salud["regular"],
            riesgo["alto"],
            label="DF23",
        ),
        ctrl.Rule(
            imc["moderadamente_elevado"] & estabilidad["poco_estable"] & tabaco["si"],
            riesgo["alto"],
            label="DF24",
        ),
        ctrl.Rule(complicaciones_qx["si"] & cicatriz_mala["si"], riesgo["alto"], label="DF25"),
    ]

    sistema = ctrl.ControlSystem(rules)
    return ctrl.ControlSystemSimulation(sistema)


_SISTEMA_CACHE: ctrl.ControlSystemSimulation | None = None


def _obtener_simulacion() -> ctrl.ControlSystemSimulation:
    """
    Devuelve la simulación del sistema difuso, construyéndola una sola vez (caché).

    Tras cambiar etiquetas o reglas en ``_construir_sistema_difuso``, reinicie
    el proceso del servidor para forzar la reconstrucción.
    """
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
    if mt.estabilidad_peso >= 4:
        n += 1
    if 4 <= mt.estado_general_salud <= 7:
        n += 1
    if mt.antecedentes_quirurgicos == "cirugía previa con complicaciones":
        n += 1
    if _es_cicatrizacion_mala(mt.cicatrizacion):
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


def _orden_codigo_regla(codigo: str) -> tuple:
    """
    Ordena etiquetas para la salida humana: primero la fase del motor, luego DF
    numéricas y finalmente las R del documento.
    """
    if codigo.startswith("Fase"):
        return (0, codigo)
    if codigo.startswith("DF") and len(codigo) > 2 and codigo[2:].isdigit():
        return (1, int(codigo[2:]))
    if codigo.startswith("R") and codigo[1:].isdigit():
        return (2, int(codigo[1:]))
    return (3, codigo)


def _regla_activada_corte_domino(codigo: str) -> ReglaActivada:
    """Arma el objeto explicativo para reglas duras de las Fases 1 y 2 (R1–R7)."""
    if codigo == "R1":
        return ReglaActivada(
            codigo=codigo,
            categoria="informacion",
            descripcion=descripcion_dominio(codigo),
        )
    return ReglaActivada(
        codigo=codigo,
        categoria="corte_prioritario",
        descripcion=descripcion_dominio(codigo),
    )


def _explicacion_texto_corte(codigo: str, aptitud: Aptitud, nivel: NivelRiesgoCat) -> str:
    """Genera el párrafo «por qué» cuando el motor se detiene en R1 o R2–R7."""
    base = descripcion_dominio(codigo)
    if codigo == "R1":
        return (
            f"La salida «{aptitud}» corresponde a la regla R1: {base} "
            "No se invoca el bloque difuso hasta completar la memoria de trabajo."
        )
    return (
        f"La salida «{aptitud}» con riesgo {nivel} corresponde a la regla prioritaria {codigo}: {base} "
        "Estas exclusiones se evalúan antes que las reglas Mamdani de riesgo gradual."
    )


def _explicacion_texto_difuso(
    aptitud: Aptitud,
    nivel: NivelRiesgoCat,
    riesgo_ajustado: float,
    moderados: int,
    disparos: list[tuple[str, float]],
    codigos_traza: list[str],
) -> str:
    """Genera el párrafo «por qué» cuando participa la defuzzificación y las trazas R8–R22."""
    principales = ", ".join(f"{c} (activación {g:.2f})" for c, g in disparos[:7])
    sufijo = " …" if len(disparos) > 7 else ""
    traza_txt = ", ".join(codigos_traza) if codigos_traza else "sin códigos R de trazabilidad"
    return (
        "No se activaron exclusiones inmediatas (R2–R7). "
        f"El subsistema difuso aportó principalmente: {principales}{sufijo}. "
        f"El postproceso por conteo de factores moderados (R21–R22) con valor {moderados} ajustó el riesgo "
        f"a {riesgo_ajustado:.1f}/100, categoría «{nivel}» y por tanto «{aptitud}». "
        f"Referencias explícitas de dominio en este caso: {traza_txt}."
    )


def evaluar_paciente(mt: MemoriaTrabajo) -> EvaluacionResultado:
    """
    Punto de entrada del razonamiento: encadenamiento hacia adelante en tres capas
    (información, reglas críticas, motor difuso + trazas) y construcción del subsistema
    de explicación para auditoría clínica o académica.
    """
    reglas: list[str] = []
    recomendaciones: list[str] = []

    # ----- Fase 1: R1 (información incompleta bloquea el resto del motor) -----
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
            reglas_explicadas=[_regla_activada_corte_domino("R1")],
            explicacion_conclusion=_explicacion_texto_corte("R1", "requiere mayor información", "medio"),
        )

    # ----- Fase 2: R2–R7 (cortes duros conclusivos antes del difuso) -----
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
            reglas_explicadas=[_regla_activada_corte_domino("R2")],
            explicacion_conclusion=_explicacion_texto_corte("R2", "no apto preliminarmente", "alto"),
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
            reglas_explicadas=[_regla_activada_corte_domino("R3")],
            explicacion_conclusion=_explicacion_texto_corte("R3", "no apto preliminarmente", "alto"),
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
            reglas_explicadas=[_regla_activada_corte_domino("R4")],
            explicacion_conclusion=_explicacion_texto_corte("R4", "no apto preliminarmente", "alto"),
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
            reglas_explicadas=[_regla_activada_corte_domino("R5")],
            explicacion_conclusion=_explicacion_texto_corte("R5", "no apto preliminarmente", "alto"),
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
            reglas_explicadas=[_regla_activada_corte_domino("R6")],
            explicacion_conclusion=_explicacion_texto_corte("R6", "no apto preliminarmente", "alto"),
        )

    if _es_salud_mala(mt.estado_general_salud):
        reglas.append("R7")
        return EvaluacionResultado(
            aptitud_preliminar="no apto preliminarmente",
            nivel_riesgo="alto",
            nivel_riesgo_numerico=93.0,
            recomendacion="Estado general de salud malo: se requiere evaluación y optimización médica previa.",
            derivacion_sugerida="médico clínico",
            reglas_activadas=reglas,
            reglas_explicadas=[_regla_activada_corte_domino("R7")],
            explicacion_conclusion=_explicacion_texto_corte("R7", "no apto preliminarmente", "alto"),
        )

    # ----- Fase 3–5: motor difuso (Mamdani + centroide) y postproceso R21–R22 -----
    sim = _obtener_simulacion()
    sim.input["edad"] = float(mt.edad)
    sim.input["imc"] = float(mt.imc)
    sim.input["estabilidad"] = float(mt.estabilidad_peso)
    sim.input["salud"] = float(mt.estado_general_salud)
    sim.input["expectativas"] = _expectativas_a_escala(mt.expectativas)
    sim.input["tabaco"] = 1.0 if mt.tabaquismo else 0.0
    sim.input["complicaciones_qx"] = (
        1.0 if mt.antecedentes_quirurgicos == "cirugía previa con complicaciones" else 0.0
    )
    sim.input["cicatriz_mala"] = _cicatrizacion_mala_factor(mt.cicatrizacion)
    sim.input["proc_abdom"] = (
        1.0 if mt.procedimiento_deseado in ("abdominoplastía", "ambos") else 0.0
    )

    sim.compute()
    riesgo_crisp = float(sim.output["riesgo"])

    moderados = _contar_factores_moderados(mt)
    riesgo_ajustado = _ajuste_r21_r22(riesgo_crisp, moderados)
    nivel = _riesgo_categoria_documento(riesgo_ajustado)
    aptitud = _clasificacion_aptitud_sin_criticos(riesgo_ajustado, nivel, moderados)

    # Trazas simbólicas de dominio (R8–R22) y etiqueta de fase del motor
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
    if _es_peso_poco_estable(mt.estabilidad_peso):
        reglas.append("R11")
    if _es_peso_inestable(mt.estabilidad_peso):
        reglas.append("R12")
    if mt.antecedentes_quirurgicos == "cirugía previa con complicaciones":
        reglas.append("R13")
    if _es_cicatrizacion_mala(mt.cicatrizacion):
        reglas.append("R14")
    if mt.estado_psicologico == "dudoso":
        reglas.append("R15")
    if mt.expectativas == "poco claras":
        reglas.append("R16")
    if mt.procedimiento_deseado in ("abdominoplastía", "ambos") and _es_peso_inestable(mt.estabilidad_peso):
        reglas.append("R17")
    if mt.procedimiento_deseado in ("abdominoplastía", "ambos") and _es_cicatrizacion_mala(mt.cicatrizacion):
        reglas.append("R18")
    if (
        mt.procedimiento_deseado == "liposucción"
        and mt.estado_general_salud >= 8
        and mt.imc <= 30
        and mt.expectativas == "realistas"
        and nivel == "bajo"
    ):
        reglas.append("R19")
    if mt.procedimiento_deseado == "ambos" and moderados >= 2:
        reglas.append("R20")

    # Reglas difusas con grado de disparo (lectura post ``compute``)
    disparos_df = disparos_difusos_desde_simulacion(sim)
    for codigo_df, _ in disparos_df:
        reglas.append(codigo_df)

    codigos_ordenados = sorted(set(reglas), key=_orden_codigo_regla)

    # ----- Subsistema de explicación: lista estructurada + párrafo «por qué» -----
    explicadas: list[ReglaActivada] = [
        ReglaActivada(
            codigo="FASE3-5",
            categoria="informacion",
            descripcion="Ejecución del controlador difuso (fuzzificación, reglas Mamdani, defuzzificación por centroide).",
        )
    ]
    for codigo_df, grado in disparos_df:
        explicadas.append(
            ReglaActivada(
                codigo=codigo_df,
                categoria="difusa_mamdani",
                descripcion=descripcion_difusa(codigo_df),
                grado_activacion=round(grado, 4),
            )
        )
    if "R21" in reglas:
        explicadas.append(
            ReglaActivada(
                codigo="R21",
                categoria="postproceso_numerico",
                descripcion=descripcion_dominio("R21"),
            )
        )
    if "R22" in reglas:
        explicadas.append(
            ReglaActivada(
                codigo="R22",
                categoria="postproceso_numerico",
                descripcion=descripcion_dominio("R22"),
            )
        )
    traza_rs = sorted(
        (r for r in reglas if r.startswith("R") and r not in ("R21", "R22")),
        key=lambda z: int(z[1:]),
    )
    for tr in traza_rs:
        explicadas.append(
            ReglaActivada(
                codigo=tr,
                categoria="trazabilidad_dominio",
                descripcion=descripcion_dominio(tr),
            )
        )

    explicacion = _explicacion_texto_difuso(
        aptitud, nivel, riesgo_ajustado, moderados, disparos_df, traza_rs
    )

    # ----- Recomendación textual (mensajes orientativos para el usuario final) -----
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
    if _es_peso_inestable(mt.estabilidad_peso):
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
        reglas_activadas=codigos_ordenados,
        reglas_explicadas=explicadas,
        explicacion_conclusion=explicacion,
    )


@app.get("/")
def raiz() -> dict[str, str]:
    """Expone metadatos mínimos; la evaluación clínica vive en ``POST /evaluar``."""
    return {
        "mensaje": "Sistema Experto API activa.",
        "probar_interfaz": "/docs",
        "salud": "/health",
        "evaluar": "POST /evaluar (cuerpo JSON según MemoriaTrabajo)",
    }


@app.post("/evaluar", response_model=EvaluacionResultado)
def endpoint_evaluar(memoria: MemoriaTrabajo) -> EvaluacionResultado:
    """Endpoint principal: transforma la memoria de trabajo en conclusión explicada."""
    return evaluar_paciente(memoria)


@app.get("/health")
def health() -> dict[str, str]:
    """Comprobación liviana para balanceadores o scripts de despliegue."""
    return {"status": "ok"}
