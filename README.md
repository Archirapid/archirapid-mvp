# Python Project

This is a Python project created with a basic structure.

## Project Structure

```
.
├── src/           # Source code files
├── tests/         # Test files
├── requirements.txt   # Project dependencies
└── README.md      # Project documentation
```

## Getting Started

1. Create a virtual environment:
   ```
   python -m venv venv
   ```

2. Activate the virtual environment:
   - Windows:
     ```
     .\venv\Scripts\activate
     ```
   - Unix/MacOS:
     ```
     source venv/bin/activate
     ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Development

Place your source code in the `src` directory and tests in the `tests` directory.

## Variables de entorno y claves API ⚠️

El proyecto utiliza **claves y secretos** (Gemini, Groq, OpenRouter, etc.) que **no deben estar en el control de versiones**. Se emplea `python-dotenv` para cargar un fichero `.env` local y Streamlit puede leer `st.secrets` en producción.

1. Copia el fichero de ejemplo:
   ```bash
   cp .env.example .env
   ```
2. Rellena los valores con tus claves privadas. Ejemplo:
   ```dotenv
   GEMINI_API_KEY=sk_...
   OPENROUTER_API_KEY=sk_...
   GROQ_API_KEY=sk_...
   ```
3. **Nunca** subas `.env` al repositorio; ya está incluido en `.gitignore`.
   Puedes comprobar que no está trackeado con:
   ```bash
   git ls-files --error-unmatch .env || echo ".env not tracked"
   ```
4. Si accidentalmente añadiste credenciales, elimínalas de la historia con `git rm --cached .env` y fuerza un nuevo commit.

Además, **no compartas** las claves en capturas de pantalla, logs o el código fuente.

Esta sección refuerza la práctica de mantener los secretos fuera del repositorio y proteger los servicios de IA.


## ⚠️ Estructura Crítica del Proyecto

### Ubicación Crítica: `compute_edificability.py`
Este archivo **DEBE** permanecer siempre en la **raíz** del proyecto. Todos los módulos de ArchiRapid dependen de esta ubicación para acceder a los datos de edificabilidad validados.

**❌ NO mover a subcarpetas** - Si se mueve, los módulos no podrán encontrar los m² exactos.

### Verificación de Integridad
Para verificar que el proyecto está correctamente configurado:
```bash
python verify_integrity.py
```

Este script confirmará que `compute_edificability.py` está en la ubicación correcta y que todos los archivos relacionados están presentes.