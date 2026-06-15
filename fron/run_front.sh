#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Instalando dependencias del frontend Node..."
npm install

echo "Sirviendo el frontend en http://127.0.0.1:5500..."
npm start
