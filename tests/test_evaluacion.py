"""
Casos de prueba del motor de inferencia y del subsistema de explicación.

Cada bloque comprueba un escenario documentado (R1, cortes R2–R7 o camino difuso)
y valida que la API pueda justificar la conclusión mediante ``reglas_explicadas``
y ``explicacion_conclusion``.
"""

from __future__ import annotations

from main import MemoriaTrabajo, evaluar_paciente


def _paciente_base(**kwargs) -> MemoriaTrabajo:
    """
    Genera una memoria de trabajo «casi sana» para mutar solo los campos relevantes.

    Evita repetir el mismo diccionario en cada prueba y documenta el perfil base.
    """
    defaults: dict = {
        "edad": 38,
        "procedimiento_deseado": "liposucción",
        "imc": 24.0,
        "estabilidad_peso": 4,
        "estado_general_salud": 8,
        "enfermedad_no_controlada": False,
        "tabaquismo": False,
        "consume_drogas": False,
        "antecedentes_quirurgicos": "sin antecedentes",
        "cicatrizacion": 4,
        "estado_psicologico": "estable",
        "expectativas": "realistas",
        "informacion_completa": True,
    }
    defaults.update(kwargs)
    return MemoriaTrabajo(**defaults)


def test_r1_informacion_incompleta_detiene_motor():
    """
    R1: sin datos completos no debe ejecutarse el difuso; solo debe figurar R1 en la traza.
    """
    mt = _paciente_base(informacion_completa=False)
    res = evaluar_paciente(mt)
    assert res.aptitud_preliminar == "requiere mayor información"
    assert res.reglas_activadas == ["R1"]
    assert len(res.reglas_explicadas) == 1
    assert res.reglas_explicadas[0].codigo == "R1"
    assert res.reglas_explicadas[0].categoria == "informacion"
    assert "R1" in res.explicacion_conclusion


def test_r3_enfermedad_no_controlada_es_corte_prioritario():
    """
    R3: enfermedad no controlada fuerza no apto y riesgo alto antes del bloque difuso.
    """
    mt = _paciente_base(enfermedad_no_controlada=True)
    res = evaluar_paciente(mt)
    assert res.aptitud_preliminar == "no apto preliminarmente"
    assert "R3" in res.reglas_activadas
    assert res.reglas_explicadas[0].categoria == "corte_prioritario"
    assert "R3" in res.explicacion_conclusion
    assert not any(r.codigo.startswith("DF") for r in res.reglas_explicadas)


def test_camino_difuso_incluye_reglas_df_y_grado():
    """
    Perfil que atraviesa el motor Mamdani: deben listarse reglas DF con grado numérico.
    """
    mt = _paciente_base(
        procedimiento_deseado="abdominoplastía",
        imc=29.0,
        estabilidad_peso=5,
        tabaquismo=True,
    )
    res = evaluar_paciente(mt)
    assert "Fase3-Fase5-difuso" in res.reglas_activadas
    dfs = [r for r in res.reglas_activadas if r.startswith("DF")]
    assert dfs, "Se esperaban códigos DF en la lista compacta"
    explicadas_df = [e for e in res.reglas_explicadas if e.categoria == "difusa_mamdani"]
    assert explicadas_df, "El subsistema de explicación debe incluir filas difusas"
    assert explicadas_df[0].grado_activacion is not None
    assert res.explicacion_conclusion
    assert "difuso" in res.explicacion_conclusion.lower() or "DF" in res.explicacion_conclusion


def test_r21_aparece_con_dos_factores_moderados():
    """
    R21: exactamente dos factores moderados (tabaco + IMC límite) disparan el piso numérico R21.
    """
    mt = _paciente_base(
        procedimiento_deseado="liposucción",
        imc=25.0,
        estabilidad_peso=3,
        estado_general_salud=9,
        tabaquismo=True,
    )
    res = evaluar_paciente(mt)
    assert "R21" in res.reglas_activadas
    assert "R22" not in res.reglas_activadas
    codigos_expl = [e.codigo for e in res.reglas_explicadas]
    assert "R21" in codigos_expl
    assert any(e.categoria == "postproceso_numerico" and e.codigo == "R21" for e in res.reglas_explicadas)
