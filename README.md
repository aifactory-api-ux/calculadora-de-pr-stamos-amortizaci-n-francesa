# loan-lib — Cálculo de préstamos con amortización francesa

Librería Python mínima para el cálculo de la cuota fija (sistema de amortización
francés) y de su cronograma de amortización.

- **Sin dependencias de runtime:** todo el cálculo se apoya en `decimal` de la
  biblioteca estándar. Los importes nunca se computan en coma flotante: solo
  se admiten entradas `int` y `Decimal`, y un `float` se rechaza con
  `TypeError` **antes** de operar.
- **Sin servidor, sin base de datos, sin interfaz:** es un módulo importable
  desde otros scripts Python.

---

## Requisitos

| Requisito | Detalle |
|---|---|
| Python | `>= 3.10, < 4.0` (usa `list[dict]` y anotaciones modernas) |
| Dependencias de runtime | Ninguna (solo `decimal` de la stdlib) |
| Dependencias de desarrollo | `pytest==8.3.4` (`pip install -e ".[dev]"`) |

La librería no lee variables de entorno, no abre sockets, no escribe archivos y
no depende de ningún servicio externo.

---

## Importación

El módulo vive en `src/loan.py` y se importa como `loan`. Hay dos formas de
usarlo:

**1. Con `src` en el `path`** (recomendado para consumo interno y para correr
los tests, ya que `pyproject.toml` configura `pythonpath = ["src"]`):

```python
import sys
sys.path.insert(0, "src")

from loan import monthly_rate, monthly_payment, amortization_schedule
```

**2. Instalando el paquete** en el entorno de trabajo:

```bash
pip install -e .
```

```python
from loan import monthly_rate, monthly_payment, amortization_schedule
```

---

## API pública

Las tres funciones son el contrato completo de la librería. Todas devuelven
valores `decimal.Decimal`; nunca se devuelven centinelas ni valores de
respaldo: una entrada inválida falla de forma explícita.

### `monthly_rate(annual_rate_pct) -> Decimal`

Convierte la tasa nominal anual **en porcentaje** a la tasa mensual equivalente
expresada como fracción.

- `monthly_rate(12)` → `Decimal("0.01")`
- `monthly_rate(0)` → `Decimal("0")`
- `monthly_rate(6)` → `Decimal("0.005")`

| Parámetro | Tipo | Descripción |
|---|---|---|
| `annual_rate_pct` | `int` \| `Decimal` | Tasa nominal anual en porcentaje, entre `0` y `100` |

**Devuelve:** la tasa mensual como fracción, sin cuantizar (hasta 28 dígitos
significativos).

**Excepciones:**
- `TypeError` — si el tipo no está admitido (`float`, `str` y `bool`
  incluidos; `bool` se rechaza aparte por ser subclase de `int`).
- `ValueError` — si la tasa es negativa, supera el `100` o no es finita.

### `monthly_payment(principal, annual_rate_pct, months) -> Decimal`

Calcula la cuota fija del préstamo.

- `monthly_payment(100000, 12, 12)` → `Decimal("8884.88")`
- `monthly_payment(1200, 0, 12)` → `Decimal("100.00")`
- `monthly_payment(1000, 0, 3)` → `Decimal("333.33")`

| Parámetro | Tipo | Descripción |
|---|---|---|
| `principal` | `int` \| `Decimal` | Capital del préstamo, no negativo (`>= 0`) |
| `annual_rate_pct` | `int` \| `Decimal` | Tasa nominal anual en porcentaje, entre `0` y `100` |
| `months` | `int` | Cantidad de cuotas, entre `1` y `480` |

**Devuelve:** la cuota fija con exactamente dos decimales. Un capital de `0`
produce `Decimal("0.00")`.

**Excepciones:**
- `TypeError` — si `principal` o `annual_rate_pct` tienen un tipo no admitido
  (`float`, `str` y `bool` incluidos), o si `months` no es un `int`.
- `ValueError` — si `principal < 0`, la tasa está fuera de `[0, 100]`, el
  plazo está fuera de `[1, 480]` o algún valor no es un número finito.

### `amortization_schedule(principal, annual_rate_pct, months) -> list[dict]`

Genera el cronograma de amortización completo: un diccionario por período.

| Clave | Tipo | Significado |
|---|---|---|
| `period` | `int` | Número de período, de `1` a `months` |
| `payment` | `Decimal` | Cuota total del período (2 decimales) |
| `interest` | `Decimal` | Parte de la cuota que corresponde a intereses |
| `principal` | `Decimal` | Parte de la cuota que amortiza el capital |
| `balance` | `Decimal` | Saldo pendiente **después** de aplicar la cuota |

Las claves se insertan siempre en ese orden y cada fila cumple estas
invariantes:

- `payment == interest + principal`
- `balance` de la fila `n` es `balance` de la fila `n - 1` menos `principal` de
  la fila `n`
- la suma de todos los `principal` es exactamente igual al capital de entrada
- el `balance` de la última fila es exactamente `Decimal("0.00")`

**Excepciones:** las mismas que `monthly_payment`.

---

## Fórmula de la cuota fija (sistema francés)

Con `P` = capital, `n` = número de cuotas e `i` = tasa mensual equivalente:

```
i     = tasa_anual_pct / 100 / 12
cuota = P * i / (1 - (1 + i) ** -n)
```

Sin tasa (`i == 0`) la fórmula se reduce a:

```
cuota = P / n
```

Los cálculos intermedios se ejecutan con `decimal.localcontext(prec=28)` para
evitar errores de coma flotante.

---

## Reglas de redondeo

- Todo importe monetario se cuantiza a **exactamente dos decimales** con
  `decimal.ROUND_HALF_UP` (el centavo residual siempre sube, no baja).
- `monthly_rate` **no** se cuantiza: devuelve la fracción con toda su
  precisión.
- Los ceros se normalizan a `Decimal("0.00")`; nunca aparece `Decimal("-0.00")`.
- **Ajuste de la última cuota:** la última fila amortiza íntegramente el saldo
  pendiente (`principal = balance`) y su cuota se recalcula como
  `principal + interest`. Con ello el saldo final es exactamente `0.00` y la
  suma del capital amortizado coincide al centavo con el capital prestado.
  Ejemplo sin tasa: `1000` en `3` cuotas produce `333.33`, `333.33` y
  `333.34`.

---

## Validación de entradas

| Entrada | Tipo admitido | Rango admitido | Errores |
|---|---|---|---|
| `principal` | `int` \| `Decimal` | `>= 0` | `TypeError` si el tipo no es admitido; `ValueError` si es negativo |
| `annual_rate_pct` | `int` \| `Decimal` | `[0, 100]` | `TypeError` si el tipo no es admitido; `ValueError` si está fuera de rango |
| `months` | `int` (excluye `bool`) | `[1, 480]` | `TypeError` si no es un `int`; `ValueError` si está fuera de rango |

Detalles adicionales:

- Solo se admiten `int` y `Decimal` en `principal` y `annual_rate_pct`; el
  `int` se normaliza con `Decimal(valor)` y el `Decimal` se conserva tal
  cual. No hay conversiones implícitas: una entrada con tipo inesperado falla
  de forma explícita en lugar de coercionarse en silencio.
- `float` y `str` se rechazan en `principal` y `annual_rate_pct` con
  `TypeError` (por ejemplo `1000.0` y `"1000"`); `bool` se rechaza también con
  `TypeError` (es subclase de `int`, por eso se trata aparte). Lo mismo ocurre
  con cualquier tipo no numérico, como `None`.
- `months` no se convierte: `12.0`, `"12"` y `True` producen `TypeError`.
- Los valores no finitos (`Decimal("NaN")`, `Decimal("Infinity")`) producen
  `ValueError`.
- Un capital de `0` es válido: la cuota es `Decimal("0.00")` y el cronograma
  contiene `months` filas íntegramente en cero, con saldo final `0.00`. Un
  capital negativo produce `ValueError`.
- Los mensajes de error indican siempre el parámetro y el valor rechazado.

---

## Ejemplo resuelto: 100000 al 12 % en 12 meses

Capital `P = 100000`, tasa nominal anual `12 %`, plazo `n = 12` cuotas.

```
i     = 12 / 100 / 12 = 0.01
cuota = 100000 * 0.01 / (1 - (1.01) ** -12) = 8884.8888...
```

Redondeando con `ROUND_HALF_UP` a dos decimales, la **cuota es `8884.88`**.

```bash
python -c "import sys; sys.path.insert(0,'src'); from loan import monthly_payment, amortization_schedule; print(monthly_payment(100000, 12, 12)); print(amortization_schedule(100000, 12, 12)[-1])"
```

Salida:

```
8884.88
{'period': 12, 'payment': Decimal('8884.85'), 'interest': Decimal('87.97'), 'principal': Decimal('8796.88'), 'balance': Decimal('0.00')}
```

**Fila 1 del cronograma** (interés `100000 * 0.01 = 1000.00`, capital amortizado
`8884.88 - 1000.00 = 7884.88`, saldo `100000 - 7884.88 = 92115.12`):

```python
{
    "period": 1,
    "payment": Decimal("8884.88"),
    "interest": Decimal("1000.00"),
    "principal": Decimal("7884.88"),
    "balance": Decimal("92115.12"),
}
```

**Cronograma completo:**

| Período | Cuota | Interés | Capital | Saldo |
|---:|---:|---:|---:|---:|
| 1 | 8884.88 | 1000.00 | 7884.88 | 92115.12 |
| 2 | 8884.88 | 921.15 | 7963.73 | 84151.39 |
| 3 | 8884.88 | 841.51 | 8043.37 | 76108.02 |
| 4 | 8884.88 | 761.08 | 8123.80 | 67984.22 |
| 5 | 8884.88 | 679.84 | 8205.04 | 59779.18 |
| 6 | 8884.88 | 597.79 | 8287.09 | 51492.09 |
| 7 | 8884.88 | 514.92 | 8369.96 | 43122.13 |
| 8 | 8884.88 | 431.22 | 8453.66 | 34668.47 |
| 9 | 8884.88 | 346.68 | 8538.20 | 26130.27 |
| 10 | 8884.88 | 261.30 | 8623.58 | 17506.69 |
| 11 | 8884.88 | 175.07 | 8709.81 | 8796.88 |
| 12 | 8884.85 | 87.97 | 8796.88 | **0.00** |

La última cuota es `8884.85` (tres centavos menos que las anteriores) porque
absorbe el saldo remanente: la suma de la columna *Capital* es exactamente
`100000.00` y el saldo final es `0.00`.

---

## Ejecución de las pruebas

```bash
python -m pytest
```

La configuración de `pyproject.toml` (`pythonpath = ["src"]` y
`testpaths = ["tests"]`) hace que el comando funcione desde la raíz del
proyecto sin instalar nada. La suite no necesita red ni servicios externos.

Para instalar las dependencias de desarrollo:

```bash
pip install -e ".[dev]"
```

El script auxiliar `run.sh` envuelve los comandos habituales:

```bash
./run.sh          # ejecuta la suite de pruebas
./run.sh --demo   # imprime el ejemplo resuelto de 100000 al 12 % en 12 meses
```

Si se dispone de Docker, la misma suite puede ejecutarse en un contenedor
limpio:

```bash
docker compose run --rm tests
```

El compose construye la imagen a partir del `Dockerfile`: el código de la
librería viaja **dentro** de la imagen y no se monta desde el host, de modo que
una imagen reconstruida ejecuta siempre el código que contiene. El único
volumen persistente es el de datos (`data:/data`), donde se guarda la caché de
paquetes; la librería no usa base de datos ni variables de entorno.

---

## Estructura del proyecto

```
.
├── pyproject.toml      # Metadatos PEP 621 y configuración de pytest
├── README.md           # Este documento
├── .gitignore          # Patrones de ignorado para Python
├── .dockerignore       # Exclusiones del contexto de build de Docker
├── Dockerfile          # Imagen con el código de la aplicación
├── docker-compose.yml  # Ejecución opcional de la suite en un contenedor
├── run.sh              # Script auxiliar: pruebas y ejemplo resuelto
├── src/
│   └── loan.py         # Módulo de la librería (superficie pública completa)
└── tests/
    └── test_loan.py    # Suite pytest
```
