# SPEC.md

## 1. TECHNOLOGY STACK

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Language | Python | >= 3.10, < 4.0 | `list[dict]` builtin generics and modern type hints are used |
| Runtime numeric type | `decimal.Decimal` (stdlib `decimal`) | stdlib | **All** monetary and rate math is `Decimal`; `float` is never used for computation |
| Rounding mode | `decimal.ROUND_HALF_UP` | stdlib | Mandatory for every quantization |
| Packaging / metadata | `pyproject.toml` (PEP 621, build backend `setuptools>=68`) | — | Declares project metadata and pytest config |
| Test framework | `pytest` | == 8.3.4 | Dev-only dependency |
| Third-party runtime dependencies | **NONE** | — | The library imports only `decimal` from the standard library |
| Linter/formatter | Not required by scope | — | Not added |

Project type: **Python library only**. No web framework, no HTTP server, no database, no frontend, no Docker, no cloud infrastructure. Those layers are explicitly out of scope because the request is a "librería Python pequeña" with three functions in `src/loan.py`.

---

## 2. DATA CONTRACTS

This is a library, so there are no ORM models. Its data contracts are (a) the function signatures and (b) the exact shape of the dictionaries returned by `amortization_schedule`.

### 2.1 Type aliases and module constants (`src/loan.py`)

```python
from decimal import Decimal
from typing import TypedDict

# Quantizer used for every monetary value: exactly 2 decimal places.
CENTS = Decimal("0.01")

# Precision used inside localcontext() for intermediate math.
CALC_PRECISION = 28

Number = int | float | str | Decimal  # accepted input types, normalized via _to_decimal
```

### 2.2 Input normalization contract

`Number` inputs (`principal`, `annual_rate_pct`) are converted with `_to_decimal(value, name)`:

* `Decimal` → returned unchanged.
* `int` / `float` / `str` → `Decimal(str(value))`.
* Anything else, or a value that is `NaN` / `Infinity` (`not d.is_finite()`), or a string that is not parseable → `ValueError(f"{name} must be a finite number, got {value!r}")`.

`months` is **not** coerced: it must be an `int` (`bool` rejected), otherwise `TypeError(f"months must be an int, got {type(months).__name__}")`.

### 2.3 `AmortizationRow` — the dict returned per period

Every element of the list returned by `amortization_schedule` is a `dict` with **exactly these five keys, in this insertion order**:

| Key | Type | Meaning | Constraints |
|---|---|---|---|
| `period` | `int` | 1-based period index | `1 <= period <= months` |
| `payment` | `Decimal` | Total amount paid in this period (cuota) | quantized to `0.01`, `ROUND_HALF_UP` |
| `interest` | `Decimal` | Interest portion of the payment | quantized to `0.01`, `ROUND_HALF_UP`, `>= 0` |
| `principal` | `Decimal` | Principal (amortization) portion of the payment | quantized to `0.01`, `ROUND_HALF_UP`, `>= 0` |
| `balance` | `Decimal` | Outstanding balance **after** this payment | quantized to `0.01`; `0.00` on the final row |

TypedDict used for documentation/typing only (runtime objects are plain `dict`):

```python
class AmortizationRow(TypedDict):
    period: int
    payment: Decimal
    interest: Decimal
    principal: Decimal
    balance: Decimal
```

Key identity rules (non-negotiable, since the consumer of this library indexes these keys literally):

* `payment == interest + principal` for **every** row (with exact `Decimal` equality, no residual rounding drift).
* `principal` values across all rows sum **exactly** to the input `principal`.
* `balance` of row `n` equals `balance` of row `n-1` minus `principal` of row `n`; the last row's `balance` is exactly `Decimal("0.00")`.
* No `Decimal("-0.00")`: any computed zero is normalized to `Decimal("0.00")`.

### 2.4 Return-type contracts of the three public functions

| Function | Return type | Guarantees |
|---|---|---|
| `monthly_rate(annual_rate_pct)` | `Decimal` | Nominal monthly rate as a **fraction** (`12` → `0.01`). Not quantized to cents; carries up to `CALC_PRECISION` significant digits. Never negative. |
| `monthly_payment(principal, annual_rate_pct, months)` | `Decimal` | Fixed installment, exactly 2 decimals (`CENTS`), `ROUND_HALF_UP`. |
| `amortization_schedule(principal, annual_rate_pct, months)` | `list[dict]` (i.e. `list[AmortizationRow]`) | Length exactly `months`; keys exactly as §2.3. |

---

## 3. API ENDPOINTS

**There are no HTTP endpoints.** The request asks for a Python library, not a service. No FastAPI/Flask app, no `/metrics`, no webhooks, no export endpoints are created — adding them would be scope invention.

The public API surface of the library is the set of module-level functions in `src/loan.py`, described here with full request/response semantics.

### 3.1 Public function API

| "Endpoint" (callable) | Signature | Inputs | Returns | Errors |
|---|---|---|---|---|
| `monthly_rate` | `monthly_rate(annual_rate_pct: Number) -> Decimal` | nominal annual rate **in percent** | monthly rate as a fraction | `ValueError` if rate negative, non-finite, or non-numeric |
| `monthly_payment` | `monthly_payment(principal: Number, annual_rate_pct: Number, months: int) -> Decimal` | loan amount, annual rate %, term in months | fixed installment, 2dp | `ValueError` if `principal < 0`, rate `< 0`, `months <= 0`; `TypeError` if `months` is not `int` |
| `amortization_schedule` | `amortization_schedule(principal: Number, annual_rate_pct: Number, months: int) -> list[dict]` | same as above | list of `AmortizationRow` dicts, length `months` | same validation errors as `monthly_payment` |

### 3.2 Detailed semantics per callable

**`monthly_rate(annual_rate_pct)`**

```
monthly_rate_pct = annual_rate_pct / 100
monthly_rate     = monthly_rate_pct / 12
```

Computed inside `decimal.localcontext()` with `prec=CALC_PRECISION` and returned **without** quantization.

* `monthly_rate(12)` → `Decimal("0.01")` (exact — required example).
* `monthly_rate(0)` → `Decimal("0")` (numerically equal to `Decimal("0.00")`).
* `monthly_rate(6)` → `Decimal("0.005")`.
* `monthly_rate(-1)` → raises `ValueError`.

**`monthly_payment(principal, annual_rate_pct, months)`**

```
i = monthly_rate(annual_rate_pct)
if i == 0:
    payment = (principal / months).quantize(CENTS, ROUND_HALF_UP)
else:
    growth = (1 + i) ** (-months)                      # Decimal ** int, inside localcontext
    payment = (principal * i / (1 - growth)).quantize(CENTS, ROUND_HALF_UP)
```

Fixed-cuota (French system) formula: `cuota = P * i / (1 - (1+i)^-n)`.

* `monthly_payment(1000, 12, 12)` → `Decimal("88.85")`.
* `monthly_payment(1200, 0, 12)` → `Decimal("100.00")`.
* `monthly_payment(1000, 0, 3)` → `Decimal("333.33")` (ROUND_HALF_UP on `333.333…`).
* `monthly_payment(-1, 12, 12)` → `ValueError`; `monthly_payment(1000, 12, 0)` → `ValueError`; `monthly_payment(1000, 12, 12.0)` → `TypeError`.

**`amortization_schedule(principal, annual_rate_pct, months)`**

Algorithm (deterministic, must be implemented exactly like this):

```
i       = monthly_rate(annual_rate_pct)
payment = monthly_payment(principal, annual_rate_pct, months)
balance = _to_decimal(principal, "principal")
rows    = []

for period in range(1, months + 1):
    if i == 0:
        interest = Decimal("0.00")
    else:
        interest = (balance * i).quantize(CENTS, ROUND_HALF_UP)

    if period == months:
        principal_part = balance                          # forces exact payoff
        row_payment    = (principal_part + interest).quantize(CENTS, ROUND_HALF_UP)
        new_balance    = Decimal("0.00")
    else:
        principal_part = (payment - interest)
        row_payment    = payment
        new_balance    = (balance - principal_part).quantize(CENTS, ROUND_HALF_UP)

    rows.append({
        "period":    period,
        "payment":   row_payment,
        "interest":  interest,
        "principal": principal_part,
        "balance":   new_balance,
    })
    balance = new_balance

return rows
```

Properties enforced by this algorithm and asserted in tests:

1. `len(result) == months`.
2. `set(row.keys()) == {"period", "payment", "interest", "principal", "balance"}` for every row.
3. `row["payment"] == row["interest"] + row["principal"]` for every row.
4. `sum(row["principal"] for row in result) == principal` (exactly, when `principal` is a 2-dp `Decimal`).
5. `result[-1]["balance"] == Decimal("0.00")`.
6. Row 1 of `amortization_schedule(1000, 12, 12)` is exactly:
   `{"period": 1, "payment": Decimal("88.85"), "interest": Decimal("10.00"), "principal": Decimal("78.85"), "balance": Decimal("921.15")}`.
7. With `annual_rate_pct=0`, every `interest` is `Decimal("0.00")` and the final row's `payment` absorbs the residual cent (e.g. `1000 / 3` → two rows of `333.33` and a last row of `333.34`).

---

## 4. FILE STRUCTURE

```
.
├── pyproject.toml          # Project metadata (name=loan-lib, requires-python>=3.10), pytest config: pythonpath=["src"], testpaths=["tests"]
├── README.md               # Short usage doc: the three functions, the fixed-rate formula, one worked example
├── .gitignore              # Python ignores: __pycache__/, *.pyc, .pytest_cache/, .venv/, dist/, build/, *.egg-info/
├── src/
│   └── loan.py             # The entire library: CENTS, CALC_PRECISION, _to_decimal, _validate,
│                           # monthly_rate, monthly_payment, amortization_schedule, __all__
└── tests/
    └── test_loan.py        # pytest suite covering all three functions, rounding, invariants, and validation errors
```

### PORT TABLE

**Not applicable** — this is a pure Python library. It opens no sockets, exposes no port, and has no Dockerfile/CMD. No host ports are allocated.

### SHARED MODULES

**Not applicable** — single module `src/loan.py`; there is no multi-service architecture and no shared directory.

Notes on files that are deliberately **not** created (scope discipline):

* No `Dockerfile`, `docker-compose.yml`, `run.sh` — containerization/deployment was not requested.
* No `.env.example` — the library reads no environment variables (§5).
* No `src/__init__.py` — `src/loan.py` is imported as the top-level module `loan` via `pythonpath = ["src"]`; adding a package layer would change the import path the request names (`src/loan.py` → `from loan import …`).
* No database, cache, message broker, metrics, tracing, or frontend files.

---

## 5. ENVIRONMENT VARIABLES

**The library requires zero environment variables.** It performs no I/O: no network calls, no file reads, no database connections, no logging configuration. Adding any env var would be an unscoped feature.

| Name | Type | Required | Description | Example |
|---|---|---|---|---|
| — | — | — | *No environment variables are read or required.* | — |

Consequences for the build: tests must pass with an empty environment; no `.env.example` file exists; `pyproject.toml` contains no runtime configuration keys.

---

## 6. IMPORT CONTRACTS

`src/loan.py` exports (declared in `__all__`):

```python
__all__ = ["monthly_rate", "monthly_payment", "amortization_schedule", "CENTS"]
```

Exact import forms consumers (and tests) must use:

```python
from loan import monthly_rate
from loan import monthly_payment
from loan import amortization_schedule
from loan import CENTS
# combined form used at the top of tests/test_loan.py:
from loan import CENTS, amortization_schedule, monthly_payment, monthly_rate
```

| Symbol | Kind | Signature / value |
|---|---|---|
| `monthly_rate` | function | `(annual_rate_pct: Number) -> Decimal` |
| `monthly_payment` | function | `(principal: Number, annual_rate_pct: Number, months: int) -> Decimal` |
| `amortization_schedule` | function | `(principal: Number, annual_rate_pct: Number, months: int) -> list[dict]` |
| `CENTS` | module constant | `Decimal("0.01")` |

Private helpers (not exported, still defined in `src/loan.py`, used by the public functions):

| Symbol | Kind | Signature |
|---|---|---|
| `_to_decimal` | function | `(value: object, name: str) -> Decimal` |
| `_validate_loan_inputs` | function | `(principal: Decimal, annual_rate_pct: Decimal, months: int) -> None` |

The import path `loan` resolves because `pyproject.toml` sets:

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

---

## 7. FRONTEND STATE & COMPONENT CONTRACTS

**Not applicable.** The project contains no frontend: no React/Vue/Angular/Svelte code, no hooks, no components, no shared UI state. The deliverable is a Python module consumed by other Python code.

---

## 8. FILE EXTENSION CONVENTION

* Language: **Python** — the project is Python-only.
* Every source, test, and config file that contains code uses the `.py` extension: `src/loan.py`, `tests/test_loan.py`. Configuration uses `.toml` (`pyproject.toml`) and `.md` (`README.md`).
* No `.js`, `.jsx`, `.ts`, `.tsx` files exist anywhere in the repository.
* **Entry point:** `src/loan.py` — this is the single module the user imports. There is no `index.html`, no `<script src>`, and no application bootstrap; the library is consumed via `from loan import monthly_rate, monthly_payment, amortization_schedule`.

---

## 9. DESIGN TOKENS

**Not applicable.** No UI/UX Design Implementation Contract was provided and the project has no user interface, so no `frontend/src/styles/tokens.ts` and no token values exist.

---

## 10. FUNCTIONAL REQUIREMENTS COVERAGE

| # | Requirement (from the request) | Implementation | Files |
|---|---|---|---|
| 1 | Small Python library for loan calculation | Single stdlib-only module, no deps, `__all__` with 3 public functions | `src/loan.py`, `pyproject.toml` |
| 2 | French amortization (fixed installment / cuota fija) | `monthly_payment` uses `P·i / (1 − (1+i)^−n)`; `amortization_schedule` amortizes with constant `payment` except the adjusted last row | `src/loan.py` |
| 3 | Code lives in `src/loan.py` | Module path exactly `src/loan.py`; imported as `loan` via `pythonpath=["src"]` | `src/loan.py` |
| 4 | `monthly_rate(annual_rate_pct) -> Decimal` | Returns `Decimal`, divides pct by 100 then by 12 in `localcontext(prec=28)` | `src/loan.py` |
| 5 | Annual **percent** rate → monthly rate, `12 -> Decimal("0.01")` | `annual_rate_pct / 100 / 12`; exact for `12`; test asserts `monthly_rate(12) == Decimal("0.01")` | `src/loan.py`, `tests/test_loan.py` |
| 6 | `monthly_payment(principal, annual_rate_pct, months) -> Decimal` | Fixed-cuota formula, returns `Decimal` quantized to `CENTS` | `src/loan.py` |
| 7 | Payment rounded to 2 decimals with `ROUND_HALF_UP` | `.quantize(CENTS, rounding=ROUND_HALF_UP)` on every returned money value | `src/loan.py` |
| 8 | Zero-rate case: payment is `principal/months` rounded | `if i == 0:` branch → `(principal / months).quantize(CENTS, HALF_UP)` | `src/loan.py` |
| 9 | `amortization_schedule(principal, annual_rate_pct, months) -> list[dict]` | Returns `list` of plain `dict` rows, one per period | `src/loan.py` |
| 10 | Row keys `period`, `payment`, `interest`, `principal`, `balance` | Dict literal built in that exact key order for every row; keys asserted in tests | `src/loan.py`, `tests/test_loan.py` |
| 11 | Interest per period derived from outstanding balance | `interest = (balance * i).quantize(CENTS, HALF_UP)`, `0.00` when rate is 0 | `src/loan.py` |
| 12 | Exact payoff on the final period (no residual balance) | Last row: `principal_part = balance`, `payment = principal_part + interest`, `balance = Decimal("0.00")` | `src/loan.py` |
| 13 | `payment == interest + principal` on every row | `principal_part = payment - interest` for non-final rows | `src/loan.py` |
| 14 | Input validation (rate ≥ 0, principal ≥ 0, months ≥ 1 int) | `_validate_loan_inputs` raises `ValueError`/`TypeError` with explicit messages | `src/loan.py` |
| 15 | Numeric inputs accepted as int/float/str/Decimal | `_to_decimal` normalizes via `Decimal(str(...))`, rejects non-finite values | `src/loan.py` |
| 16 | Requested tests | `tests/test_loan.py` with pytest cases listed in §10.1 below | `tests/test_loan.py` |
| 17 | Usable documentation | `README.md` with the three signatures, the formula, and a worked 1000/12%/12 example | `README.md` |
| 18 | Reproducible test invocation | `pyproject.toml` `[tool.pytest.ini_options]` with `pythonpath=["src"]`, `testpaths=["tests"]` | `pyproject.toml` |

### 10.1 Test cases required in `tests/test_loan.py`

`monthly_rate`:
1. `monthly_rate(12) == Decimal("0.01")` (explicit requirement example).
2. `monthly_rate(0) == Decimal("0")`.
3. `monthly_rate(6) == Decimal("0.005")`.
4. `monthly_rate(-1)` raises `ValueError`.
5. `monthly_rate("abc")` raises `ValueError`.
6. `isinstance(monthly_rate(12), Decimal)` is `True`.

`monthly_payment`:
7. `monthly_payment(1000, 12, 12) == Decimal("88.85")` (ROUND_HALF_UP, 2dp).
8. `monthly_payment(1200, 0, 12) == Decimal("100.00")` (zero-rate branch).
9. `monthly_payment(1000, 0, 3) == Decimal("333.33")` (half-up on `333.333…`).
10. `monthly_payment(1000, 12, 12).as_tuple().exponent == -2` (exactly 2 decimals).
11. `monthly_payment(-1, 12, 12)` raises `ValueError`.
12. `monthly_payment(1000, -1, 12)` raises `ValueError`.
13. `monthly_payment(1000, 12, 0)` raises `ValueError`.
14. `monthly_payment(1000, 12, 12.0)` raises `TypeError`.

`amortization_schedule`:
15. `len(amortization_schedule(1000, 12, 12)) == 12`.
16. Every row's key set is exactly `{"period","payment","interest","principal","balance"}` and `row["period"] == index + 1`.
17. Row 1 of `(1000, 12, 12)` equals `{"period":1,"payment":Decimal("88.85"),"interest":Decimal("10.00"),"principal":Decimal("78.85"),"balance":Decimal("921.15")}`.
18. For every row: `row["payment"] == row["interest"] + row["principal"]`.
19. `sum(row["principal"] for row in rows) == Decimal("1000.00")` for `(1000, 12, 12)`.
20. `rows[-1]["balance"] == Decimal("0.00")`.
21. Zero-rate schedule `(1000, 0, 3)` → interests all `Decimal("0.00")`, payments `[333.33, 333.33, 333.34]`, last balance `0.00`.
22. `amortization_schedule(1000, 12, 0)` raises `ValueError`; `amortization_schedule(1000, 12, "12")` raises `TypeError`.

### 10.2 Failure honesty

No external service, API key, or unavailable dependency is required by this scope, so nothing is stubbed or mocked. The library never returns placeholder values: every function computes real results from its inputs, and invalid inputs fail loudly with `ValueError`/`TypeError` instead of returning sentinel data.