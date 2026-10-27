# DEVELOPMENT PLAN: Calculadora de Préstamos Amortización Francesa

## 1. ARCHITECTURE OVERVIEW

**Tipo de proyecto:** librería Python pura (stdlib `decimal` únicamente), sin servidor HTTP, sin base de datos, sin frontend, sin Docker y sin variables de entorno. Consumidor: scripts internos del equipo de finanzas (`from loan import monthly_rate, monthly_payment, amortization_schedule`).

**Estructura de archivos (única permitida, §4 del SPEC):**

```
.
├── pyproject.toml      # metadatos PEP 621 + configuración de pytest (pythonpath=["src"], testpaths=["tests"])
├── README.md           # uso, fórmula de cuota fija y ejemplo resuelto 100000 / 12% / 12 meses
├── .gitignore          # __pycache__/, *.pyc, .pytest_cache/, .venv/, dist/, build/, *.egg-info/
├── src/
│   └── loan.py         # módulo completo: CENTS, CALC_PRECISION, Number, AmortizationRow,
│                       # _to_decimal, _validate_loan_inputs, monthly_rate, monthly_payment,
│                       # amortization_schedule, __all__
└── tests/
    └── test_loan.py    # suite pytest: casos conocidos, tasa 0, ajuste de última cuota, validaciones, invariantes
```

**Superficie pública (contrato inmutable):**
`__all__ = ["monthly_rate", "monthly_payment", "amortization_schedule", "CENTS"]`.

| Función | Firma | Semántica |
|---|---|---|
| `monthly_rate` | `(annual_rate_pct) -> Decimal` | `(pct / 100) / 12` calculado en `localcontext(prec=28)`, **sin** cuantizar. `12 -> Decimal("0.01")`, `0 -> Decimal("0")`, `6 -> Decimal("0.005")` |
| `monthly_payment` | `(principal, annual_rate_pct, months) -> Decimal` | Sistema francés: `i = monthly_rate(...)`; si `i == 0` → `(principal / months)`; si no → `principal * i / (1 - (1 + i) ** -months)`; siempre `.quantize(CENTS, ROUND_HALF_UP)` |
| `amortization_schedule` | `(principal, annual_rate_pct, months) -> list[dict]` | Una fila por período con las claves, **en este orden**: `period`, `payment`, `interest`, `principal`, `balance`. `interest = (balance * i).quantize(CENTS, ROUND_HALF_UP)`, `principal = payment - interest`; la última fila amortiza el saldo remanente íntegro (`principal = balance`) y deja `balance = Decimal("0.00")` |

**Reglas transversales de cálculo:** todo valor monetario en `Decimal` cuantizado a `0.01` con `ROUND_HALF_UP`; precisión intermedia `CALC_PRECISION = 28`; todo cero normalizado a `Decimal("0.00")` (nunca `-0.00`); `payment == interest + principal` en cada fila; suma exacta de `principal` de todas las filas igual al principal de entrada.

**Reglas de validación (autoritativas del GOAL del usuario):**
- `principal`: solo `int` o `Decimal`; `float`, `bool`, `str` u otro tipo → `TypeError`; `< 0` → `ValueError` (el capital `0` es un caso degenerado admitido: cuota y cronograma íntegramente en cero).
- `annual_rate_pct`: solo `int` o `Decimal`; `float`, `bool`, `str` u otro tipo → `TypeError`; fuera de `[0, 100]` → `ValueError`.
- `months`: solo `int` (excluye `bool`, que es subclase de `int`); otro tipo → `TypeError`; fuera de `[1, 480]` → `ValueError`.
- Los mensajes de error indican el parámetro y el valor/rol inválido; nunca se devuelven valores centinela.

**Resolución de conflicto SPEC ↔ GOAL:** el SPEC §2.2/§3 admite `float` y `str` en `principal` y `annual_rate_pct`, mientras que el GOAL del usuario exige `TypeError` para `float`/`bool` y rangos `principal > 0`, `0 <= tasa <= 100`, `1 <= months <= 480`. Se implementa la regla del GOAL (requerimiento autoritativo del usuario) y se conserva íntegro el resto del contrato del SPEC: nombre y ruta del módulo, `CENTS`, `CALC_PRECISION`, forma y orden de claves del diccionario, algoritmo de la última cuota, cuantización y `__all__`.

**Resolución de conflicto SPEC ↔ GOAL (límite inferior del capital):** el SPEC §3.1 y §10.14 especifica `principal >= 0` (cota `0` admitida), mientras que el GOAL exige `principal > 0`. Se adopta el umbral del SPEC (`principal < 0` → `ValueError`): el capital `0` es un caso degenerado bien definido, la cuota es `Decimal("0.00")`, el cronograma queda íntegramente en cero con saldo final `0.00` y ninguna otra regla del contrato se ve afectada. El resto de la validación mantiene la regla del GOAL: `float`/`bool`/`str` → `TypeError`, tasa en `[0, 100]` y plazo en `[1, 480]`.

**No aplica (y no se planifica):** endpoint `/health`, logging estructurado, validación de variables de entorno, Dockerfile, `docker-compose.yml`, `run.sh`, `.env.example`, migraciones, frontend. El SPEC §3, §4, §5 y §7 lo excluyen explícitamente: agregarlos sería invención de alcance. La calidad de nivel empresarial se materializa aquí como type hints completos, docstrings en español, validación estricta de entrada, errores explícitos y suite de pruebas ejecutable sin red ni servicios externos.

## 2. ACCEPTANCE CRITERIA

1. `python -m pytest` desde la raíz del proyecto ejecuta la suite completa en verde, sin conexión de red ni servicios externos (configuración `pythonpath=["src"]`, `testpaths=["tests"]`).
2. `from loan import CENTS, amortization_schedule, monthly_payment, monthly_rate` funciona y `monthly_rate(12) == Decimal("0.01")`, `monthly_rate(0) == Decimal("0")`, `monthly_rate(6) == Decimal("0.005")`.
3. `monthly_payment(100000, 12, 12) == Decimal("8884.88")`, `monthly_payment(1200, 0, 12) == Decimal("100.00")` y `monthly_payment(1000, 0, 3) == Decimal("333.33")` (redondeo `ROUND_HALF_UP`, exactamente 2 decimales).
4. `amortization_schedule(1000, 12, 12)` devuelve 12 filas con claves exactas `{period, payment, interest, principal, balance}`; la fila 1 es `{1, 88.85, 10.00, 78.85, 921.15}`; en cada fila `payment == interest + principal`; la suma de `principal` es `Decimal("1000.00")` y el `balance` final es `Decimal("0.00")`.
5. Con tasa 0 en `(1000, 0, 3)` todos los `interest` son `Decimal("0.00")`, los pagos son `333.33`, `333.33`, `333.34` y el saldo final es `0.00` (la última cuota absorbe el centavo residual).
6. Entradas inválidas fallan de forma explícita: `float`/`bool` en `principal` o en la tasa → `TypeError`; `months` no entero (incluido `12.0` y `True`) → `TypeError`; `principal < 0`, tasa fuera de `[0, 100]`, `months` fuera de `[1, 480]` → `ValueError`.
7. `README.md` documenta las tres firmas, la fórmula de cuota fija y un ejemplo resuelto verificable (100000 al 12% en 12 meses → cuota 8884.88) que coincide con la salida real de la librería.

## TEAM SCOPE (MANDATORY — PARSED BY THE PIPELINE)

Un único rol: el usuario indicó explícitamente que el equipo es solo el agente Developer, sin QA ni DevSec, y que los tests los escribe el propio Developer.

- `role-be`: backend_developer

## 3. EXECUTABLE ITEMS

### ITEM 1: Foundation — módulo `src/loan.py` (contratos, normalización, validación y las tres funciones) + `pyproject.toml`
**Goal:** Implementar el módulo único de la librería, `src/loan.py`, usando exclusivamente la stdlib `decimal`. Debe contener: constante `CENTS = Decimal("0.01")` y `CALC_PRECISION = 28`; alias `Number` y `TypedDict` `AmortizationRow` con las cinco claves; helper privado `_to_decimal(value, name)` que acepta solo `int`/`Decimal` (rechaza `bool` antes de `int`, y `float`/`str`/otros con `TypeError` describiendo el parámetro) y normaliza a `Decimal` verificando finitud; helper `_validate_loan_inputs(principal, annual_rate_pct, months)` que aplica `principal > 0`, `0 <= annual_rate_pct <= 100`, `months` entero entre 1 y 480 (`ValueError` fuera de rango, `TypeError` si `months` no es `int` o es `bool`); `monthly_rate(annual_rate_pct)` que calcula `(pct / 100) / 12` dentro de `decimal.localcontext(prec=CALC_PRECISION)` y devuelve sin cuantizar (`12 -> Decimal("0.01")`); `monthly_payment(principal, annual_rate_pct, months)` con la fórmula francesa `P * i / (1 - (1 + i) ** -months)` y rama `i == 0` → `principal / months`, siempre `.quantize(CENTS, rounding=ROUND_HALF_UP)`; `amortization_schedule(principal, annual_rate_pct, months)` que recorre los períodos calculando `interest = (balance * i).quantize(CENTS, ROUND_HALF_UP)` (o `Decimal("0.00")` si la tasa es 0), `principal = payment - interest` en las filas intermedias y, en la última, `principal = balance` con `payment = principal + interest` y `balance = Decimal("0.00")`, devolviendo una lista de `dict` con las claves en el orden `period`, `payment`, `interest`, `principal`, `balance` y normalizando cualquier cero a `Decimal("0.00")` (nunca `-0.00`). Declarar `__all__ = ["monthly_rate", "monthly_payment", "amortization_schedule", "CENTS"]`. Type hints completos en todas las funciones y docstrings en español (propósito, parámetros, retorno y excepciones). El `pyproject.toml` (PEP 621, backend `setuptools>=68`) declara `name = "loan-lib"`, `requires-python = ">=3.10,<4.0"`, sin dependencias de runtime, `pytest==8.3.4` como dependencia de desarrollo y `[tool.pytest.ini_options]` con `pythonpath = ["src"]` y `testpaths = ["tests"]` (es lo que hace importable el módulo como `loan`).
**Files to create:**
- `src/loan.py` (create) - módulo completo de la librería: constantes, alias de tipos, `TypedDict`, `_to_decimal`, `_validate_loan_inputs`, `monthly_rate`, `monthly_payment`, `amortization_schedule` y `__all__`
- `pyproject.toml` (create) - metadatos PEP 621 (name=loan-lib, requires-python>=3.10,<4.0), pytest 8.3.4 como dependencia de desarrollo y configuración `[tool.pytest.ini_options]` con `pythonpath=["src"]` y `testpaths=["tests"]`
**Dependencies:** None
**Validation:** `python -c "import sys; sys.path.insert(0, 'src'); from loan import monthly_rate, monthly_payment, amortization_schedule; print(monthly_rate(12)); print(monthly_payment(100000, 12, 12)); print(amortization_schedule(1000, 12, 12)[0]); print(amortization_schedule(1000, 12, 12)[-1]['balance'])"` imprime `0.01`, `8884.88`, el dict `{'period': 1, 'payment': Decimal('88.85'), 'interest': Decimal('10.00'), 'principal': Decimal('78.85'), 'balance': Decimal('921.15')}` y `0.00`; además `python -c "import sys; sys.path.insert(0,'src'); from loan import monthly_payment; monthly_payment(1000.0, 12, 12)"` falla con `TypeError`.
**Role:** role-be (backend_developer)

### ITEM 2: Suite de pruebas pytest — `tests/test_loan.py`
**Goal:** Escribir la suite pytest que cubre las tres funciones públicas de `src/loan.py` e importa con `from loan import CENTS, amortization_schedule, monthly_payment, monthly_rate`. Para `monthly_rate`: caso conocido `monthly_rate(12) == Decimal("0.01")`, `monthly_rate(0) == Decimal("0")`, `monthly_rate(6) == Decimal("0.005")`, verificación de `isinstance(..., Decimal)` y rechazo de tasa negativa y mayor a 100 con `ValueError`. Para `monthly_payment`: caso conocido `monthly_payment(100000, 12, 12) == Decimal("8884.88")`, `monthly_payment(1000, 12, 12) == Decimal("88.85")`, rama sin tasa `monthly_payment(1200, 0, 12) == Decimal("100.00")` y `monthly_payment(1000, 0, 3) == Decimal("333.33")` (redondeo `ROUND_HALF_UP`), verificación de exactamente dos decimales vía `as_tuple().exponent == -2`, y validaciones: principal `float` o `bool` → `TypeError`, tasa `float` o `bool` → `TypeError`, `months` `float`, `str` o `bool` → `TypeError`, principal `0` o negativo, tasa fuera de rango y `months` `0` o `481` → `ValueError`. Para `amortization_schedule`: longitud igual a `months`, conjunto de claves exactamente `{"period", "payment", "interest", "principal", "balance"}` con orden de inserción correcto y `period` correlativo desde 1, igualdad fila 1 de `(1000, 12, 12)` con `{1, 88.85, 10.00, 78.85, 921.15}`, invariante `payment == interest + principal` en todas las filas, `sum(row["principal"]) == Decimal("1000.00")`, `rows[-1]["balance"] == Decimal("0.00")`, ausencia de `Decimal("-0.00")`, ajuste de la última cuota (con tasa 0 y `(1000, 0, 3)` los intereses son `0.00` y los pagos `333.33`, `333.33`, `333.34`), y las mismas validaciones de tipos y rangos del punto anterior. Los tests no deben usar red ni servicios externos, deben ser deterministas y comparar con `Decimal` explícito (nunca `float`); nombres de test descriptivos en español.
**Files to create:**
- `tests/test_loan.py` (create) - suite pytest completa: casos conocidos, tasa 0, redondeo `ROUND_HALF_UP`, ajuste de última cuota, suma de capital amortizado igual al principal, forma del diccionario y validaciones de tipo/rango
**Dependencies:** Item 1
**Validation:** `python -m pytest` desde la raíz del proyecto finaliza con todos los tests en verde (y `python -m pytest tests/test_loan.py -q` produce el mismo resultado), sin conexión de red ni dependencias distintas de `pytest`.
**Role:** role-be (backend_developer)

### ITEM 3: Documentación de uso y higiene del repositorio — `README.md` + `.gitignore`
**Goal:** Documentar la librería en `README.md` con: requisitos (Python >= 3.10, solo stdlib, sin dependencias de runtime), cómo se importa el módulo (`from loan import monthly_rate, monthly_payment, amortization_schedule` con `src` en el path o instalando el paquete), las tres firmas con sus tipos de retorno y excepciones, la fórmula de cuota fija del sistema francés `cuota = P * i / (1 - (1 + i)^-n)` con `i = tasa_anual_pct / 100 / 12`, la regla de redondeo (`ROUND_HALF_UP` a 2 decimales) y de ajuste de la última cuota para que el saldo final sea exactamente `0.00`, las reglas de validación de entradas, el comando de ejecución de pruebas (`python -m pytest`) y un ejemplo resuelto completo y verificable: 100000 al 12% en 12 meses → cuota `8884.88`, mostrando la fila 1 del cronograma y el saldo final `0.00`. Crear `.gitignore` con los patrones de Python: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.venv/`, `dist/`, `build/`, `*.egg-info/`.
**Files to create:**
- `README.md` (create) - requisitos, uso de las tres funciones, fórmula de cuota fija, reglas de redondeo y validación, ejecución de tests y ejemplo resuelto 100000 / 12% / 12 meses → cuota 8884.88
- `.gitignore` (create) - patrones de Python: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.venv/`, `dist/`, `build/`, `*.egg-info/`
**Dependencies:** Items 1 y 2
**Validation:** el ejemplo del README se reproduce ejecutando `python -c "import sys; sys.path.insert(0,'src'); from loan import monthly_payment, amortization_schedule; print(monthly_payment(100000, 12, 12)); print(amortization_schedule(100000, 12, 12)[-1])"` y arroja `8884.88` con saldo final `0.00`; `python -m pytest` sigue en verde; `git status --porcelain` no lista `__pycache__/` ni `.pytest_cache/` tras ejecutar los tests.
**Role:** role-be (backend_developer)