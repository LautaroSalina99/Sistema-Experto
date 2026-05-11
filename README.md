# Sistema experto — evaluación preliminar (cirugía estética corporal)

Backend en **Python (FastAPI)** + motor difuso, frontend en **React (Vite)**. Para probar todo en local hace falta **Python 3** y **Node.js** (npm).

---

## Paso a paso rápido

1. Clonar o descargar el repo y abrir una terminal en la **carpeta raíz** del proyecto (donde está `main.py` y `requirements.txt`).
2. Instalar dependencias del backend y levantar la API (**terminal 1**).
3. En otra terminal, entrar en `frontend`, instalar dependencias y levantar la web (**terminal 2**).
4. Abrir el navegador en la URL que muestre Vite (suele ser `http://localhost:5173`).
5. *(Opcional)* Ejecutar las pruebas automáticas con pytest.

Recomendación: **arrancar siempre el backend antes que el frontend**, para que el formulario pueda llamar a la API.

---

## Backend (API)

**Requisitos:** Python 3.11+ (probado con 3.13).

En la raíz del repo:

```bash
python -m pip install -r requirements.txt
```

Levantar el servidor (elige una opción):

```bash
python -m uvicorn main:app --reload
```

En Windows también puedes usar el script `run.bat` (doble clic o desde CMD/PowerShell en la raíz).

- API: `http://127.0.0.1:8000`
- Documentación interactiva (Swagger): `http://127.0.0.1:8000/docs`
- Salud: `http://127.0.0.1:8000/health`

> Si `uvicorn` no se reconoce como comando, usa siempre `python -m uvicorn` como arriba.

---

## Frontend (interfaz)

**Requisitos:** Node.js LTS y npm.

```bash
cd frontend
npm install
npm run dev
```

Abre la URL que indique la consola (normalmente `http://localhost:5173`). El frontend está configurado para hablar con la API en `http://127.0.0.1:8000` (CORS ya definido en el backend).

Compilar para producción (opcional):

```bash
npm run build
```

---

## Pruebas automáticas (pytest)

Desde la **raíz** del repo (misma carpeta que `main.py`):

```bash
python -m pip install -r requirements.txt
python -m pytest tests -v
```

Solo el archivo de evaluación:

```bash
python -m pytest tests/test_evaluacion.py -v
```

No hace falta tener el servidor corriendo: los tests importan el código directamente.

---

## Estructura útil

| Ruta | Contenido |
|------|-----------|
| `main.py` | API FastAPI, memoria de trabajo, motor de reglas y difuso |
| `explicacion_reglas.py` | Textos y lectura de disparos difusos para el subsistema de explicación |
| `frontend/` | Interfaz React + Vite |
| `tests/` | Pruebas con pytest |
