#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creando entorno virtual en $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
fi

echo "Activando entorno virtual..."
source "$VENV_DIR/bin/activate"

echo "Instalando dependencias del modelo..."
"$PIP" install --upgrade pip
"$PIP" install -r requirements.txt

echo "Entrenando el modelo con límites de memoria y streaming..."
"$PYTHON" train.py --batch-size 8 --seq-len 32 --epochs 3 --max-memory-gb 10 --validation-ratio 0.1 --max-files 10 --max-chars 150000 --step 8 "$@"

echo "Hecho. El modelo se guardará en $SCRIPT_DIR/saved_model.pt"

echo "Para usar el entorno virtual más tarde, ejecuta: source $VENV_DIR/bin/activate"
