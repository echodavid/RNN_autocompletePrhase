# Model

Carpeta para entrenamiento, experimentos y datos.

Estructura:
- `train.py`: script base de entrenamiento para un asistente de redacción en español.
- `requirements.txt`: dependencias para el entorno de modelo.
- `data/`: lugar para el corpus y archivos de texto.

Instrucciones:
1. Coloca tu corpus en `model/data/` o dentro de `model/data/dataset/`.
2. Si tu dataset está en `model/data/dataset/`, el script cargará hasta `--max-files` archivos de texto dentro de ese directorio.
3. Ejecuta `python train.py` o `./run_model.sh`.

Consejos de memoria y entrenamiento:
- Usa `--batch-size` y `--seq-len` pequeños para bajar el uso de RAM.
- El script ahora intenta aplicar un límite de memoria con `--max-memory-gb` en Linux.
- `run_model.sh` ejecuta con valores conservadores: `batch-size=8`, `seq-len=32`, `epochs=3`, `max-memory-gb=10`, `max-files=10`, `max-chars=150000`, `step=8`.
- Si el dataset es muy grande, reduce `--max-files` y `--max-chars`, o divide los archivos manualmente entre `train/` y `val/`.

El script actual es un esqueleto que carga datos y prepara el entrenamiento con PyTorch. Sustituye el modelo y la lógica con tu red recurrente o Transformer.
