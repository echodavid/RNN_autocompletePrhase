# Proyecto de Asistente de Redacción

Este proyecto está organizado en tres carpetas principales:

- `/model`: entrenamiento del modelo, datos y scripts.
- `/back`: mini API para cargar el modelo y exponer un endpoint de corrección.
- `/fron`: frontend para validar el asistente de redacción y mostrar sugerencias.

## Estructura

- `model/train.py`: script de entrenamiento base con PyTorch.
- `model/data/`: lugar para el corpus en español.
- `back/main.py`: servidor FastAPI para la API de corrección.
- `fron/index.html`: frontend sencillo para probar la corrección.

## Instrucciones rápidas

1. Copia tu dataset en `model/data/spanish_corpus.txt`.
2. Instala dependencias en el modelo: `pip install -r model/requirements.txt`.
3. Entrena o guarda el modelo con `python model/train.py`.
4. Instala dependencias del backend: `pip install -r back/requirements.txt`.
5. Inicia el backend: `uvicorn back.main:app --reload --port 8001`.
6. Abre `fron/index.html` en el navegador y prueba la interfaz.

## Ejemplo de uso

Texto de prueba:

> hola como etas

Resultado esperado:

> hola como estás
