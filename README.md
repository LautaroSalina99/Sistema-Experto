# Sistema Experto - Evaluación de Cirugías Estéticas

Este proyecto consta de un motor de inferencias desarrollado en Python (FastAPI) y una interfaz gráfica construida con React y Vite. 

Para que la aplicación funcione correctamente en tu entorno local, es necesario levantar ambos servicios en simultáneo utilizando dos terminales separadas. Se recomienda **iniciar siempre el backend primero**.

---

## ⚙️ Backend (FastAPI)

El motor del sistema experto se encuentra en la raíz del repositorio, donde está ubicado el archivo `main.py` (ej. `c:\Users\lauta\Desktop\Sistema Experto`).

### 1. Instalación de dependencias
Si es la primera vez que ejecutas el proyecto, abre una terminal en la raíz y ejecuta:
```bash
python -m pip install -r requirements.txt
```
### 2. Levantar el servidor
Una vez instaladas las dependencias, inicia la API con uvicorn:
```bash
uvicorn main:app --reload
```

- Nota: El backend quedará corriendo en `http://127.0.0.1:8000`.
- El frontend se comunicará automáticamente con el endpoint `http://127.0.0.1:8000/evaluar`.

## 💻 Frontend (Vite + React)

La interfaz de usuario se encuentra dentro de la carpeta `frontend`.

### 1. Instalación de dependencias
Abre un segunda terminal, navega a la carpeta del frontend y descarga los paquetes de Node:

```bash
cd "c:\Users\lauta\Desktop\Sistema Experto\frontend"
npm install
```
### 2. Levantar el entorno de desarrollo
Inicia la aplicación de React ejecutando:
```bash
npm run dev
```

- Nota: Nota: La interfaz gráfica suele abrirse en `http://localhost:5173`.
- Los permisos de CORS ya están configurados en el backend para permitir las peticiones desde esta dirección.

---

### Aclaraciones
Todas las funciones (base de conocimiento, motor de inferencia, etc), se encuentro dentro del archivo `main.py`
