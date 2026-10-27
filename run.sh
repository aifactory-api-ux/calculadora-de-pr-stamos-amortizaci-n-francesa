#!/usr/bin/env sh
# Script auxiliar de la librería: ejecuta la suite de pruebas y muestra el
# ejemplo resuelto documentado en el README.
# Uso: ./run.sh [--tests|--demo|--help]

set -eu

RAIZ="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$RAIZ"

PYTHON="${PYTHON:-python3}"

uso() {
    echo "Uso: ./run.sh [--tests|--demo|--help]"
    echo
    echo "  --tests  Ejecuta la suite de pruebas (opción por defecto)."
    echo "  --demo   Imprime el ejemplo resuelto de 100000 al 12 % en 12 meses."
    echo "  --help   Muestra esta ayuda."
}

ejecutar_pruebas() {
    if ! "$PYTHON" -c "import pytest" >/dev/null 2>&1; then
        echo "pytest no está disponible. Instala las dependencias con:" >&2
        echo "  pip install -e \".[dev]\"" >&2
        exit 1
    fi
    "$PYTHON" -m pytest
}

ejecutar_demo() {
    PYTHONPATH="$RAIZ/src${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON" - <<'PY'
from decimal import Decimal

from loan import amortization_schedule, monthly_payment, monthly_rate

principal = Decimal("100000")
tasa = Decimal("12")
meses = 12

print(f"tasa mensual: {monthly_rate(tasa)}")
print(f"cuota: {monthly_payment(principal, tasa, meses)}")
for fila in amortization_schedule(principal, tasa, meses):
    print(fila)
PY
}

if [ "$#" -gt 1 ]; then
    echo "Uso: ./run.sh [--tests|--demo|--help]" >&2
    exit 2
fi

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "No se encontró el intérprete '$PYTHON'. Indícalo con la variable PYTHON." >&2
    exit 1
fi

case "${1:-}" in
    "" | --tests) ejecutar_pruebas ;;
    --demo) ejecutar_demo ;;
    --help | -h) uso ;;
    *)
        echo "Opción desconocida: $1" >&2
        uso
        exit 2
        ;;
esac
