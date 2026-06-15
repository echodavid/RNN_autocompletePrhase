#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source "$SCRIPT_DIR/../model/.venv/bin/activate"

echo "Instalando dependencias del backend Python..."
python3 -m pip install -r requirements.txt

echo "Iniciando servidor Python en http://127.0.0.1:8001..."
uvicorn main:app --reload --host 127.0.0.1 --port 8001
