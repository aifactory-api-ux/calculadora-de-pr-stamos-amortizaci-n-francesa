"""Cálculo de préstamos con amortización francesa (cuota fija).

El módulo expone tres funciones públicas que operan exclusivamente con
`decimal.Decimal`, sin dependencias externas ni efectos de entorno:

* `monthly_rate`: convierte la tasa nominal anual en porcentaje a la tasa
  mensual equivalente expresada como fracción.
* `monthly_payment`: calcula la cuota fija del préstamo (sistema francés).
* `amortization_schedule`: devuelve el cronograma de amortización completo.

Todos los importes monetarios se cuantizan a dos decimales con
`decimal.ROUND_HALF_UP` y la última cuota se ajusta para que el saldo final
sea exactamente `Decimal("0.00")`.

Las entradas numéricas (`principal`, `annual_rate_pct`) admiten únicamente
`int` y `Decimal`; se normalizan a `Decimal` antes de cualquier cálculo, de
modo que la aritmética monetaria nunca se realiza en coma flotante. Cualquier
otro tipo (`float`, `str`, `bool`, ...) se rechaza con `TypeError` de forma
explícita, sin coerciones silenciosas que oculten errores del consumidor.

Rangos admitidos: capital no negativo (`0` incluido), tasa nominal anual en
`[0, 100]` y plazo entre `1` y `480` cuotas. Un capital de `0` es un caso
degenerado bien definido: la cuota y el cronograma resultantes son cero.
"""

from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import TypedDict

__all__ = ["monthly_rate", "monthly_payment", "amortization_schedule", "CENTS"]

#: Cuantizador de importes monetarios: exactamente dos decimales.
CENTS = Decimal("0.01")

#: Precisión decimal utilizada en los cálculos intermedios.
CALC_PRECISION = 28

#: Plazo máximo admitido, en meses.
MAX_MONTHS = 480

#: Tipos numéricos admitidos en las entradas (se normalizan a `Decimal`).
Number = int | Decimal


class AmortizationRow(TypedDict):
    """Fila del cronograma de amortización.

    Las claves se insertan siempre en este orden: `period`, `payment`,
    `interest`, `principal`, `balance`.
    """

    period: int
    payment: Decimal
    interest: Decimal
    principal: Decimal
    balance: Decimal


def _to_decimal(value: object, name: str) -> Decimal:
    """Normaliza un valor numérico de entrada a `Decimal`.

    Solo se admiten `int` y `Decimal`. `bool` se rechaza de forma explícita
    por ser subclase de `int`, y `float`, `str` y cualquier otro tipo
    producen `TypeError` antes de realizar ningún cálculo: una entrada con
    tipo inesperado falla de forma explícita en lugar de coercionarse en
    silencio. Los valores no finitos producen `ValueError`.

    Args:
        value: Valor de entrada a normalizar.
        name: Nombre del parámetro, usado en los mensajes de error.

    Returns:
        El valor convertido a `Decimal` finito.

    Raises:
        TypeError: Si el tipo del valor no está admitido.
        ValueError: Si el valor no es un número finito.
    """
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an int or Decimal, got bool")

    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int):
        number = Decimal(value)
    else:
        raise TypeError(
            f"{name} must be an int or Decimal, got {type(value).__name__}"
        )

    if not number.is_finite():
        raise ValueError(f"{name} must be a finite number, got {value!r}")

    return number


def _validate_loan_inputs(
    principal: Decimal, annual_rate_pct: Decimal, months: int
) -> None:
    """Valida los tipos y rangos de los parámetros de un préstamo.

    Args:
        principal: Capital del préstamo, ya normalizado a `Decimal`.
        annual_rate_pct: Tasa nominal anual en porcentaje, ya normalizada.
        months: Cantidad de cuotas del préstamo.

    Raises:
        TypeError: Si `months` no es un `int` o es un `bool`.
        ValueError: Si el capital es negativo, la tasa está fuera de
            `[0, 100]` o el plazo está fuera de `[1, 480]`.
    """
    if isinstance(months, bool) or not isinstance(months, int):
        raise TypeError(f"months must be an int, got {type(months).__name__}")

    if principal < 0:
        raise ValueError(
            f"principal must be greater than or equal to 0, got {principal}"
        )

    if annual_rate_pct < 0 or annual_rate_pct > 100:
        raise ValueError(
            f"annual_rate_pct must be between 0 and 100, got {annual_rate_pct}"
        )

    if months < 1 or months > MAX_MONTHS:
        raise ValueError(f"months must be between 1 and {MAX_MONTHS}, got {months}")


def _sin_cero_negativo(value: Decimal) -> Decimal:
    """Normaliza un importe cero para que nunca sea `Decimal("-0.00")`.

    Args:
        value: Importe a normalizar.

    Returns:
        `Decimal("0.00")` si el importe es cero; el importe original en caso
        contrario.
    """
    if value == 0:
        return Decimal("0.00")
    return value


def monthly_rate(annual_rate_pct: Number) -> Decimal:
    """Convierte la tasa nominal anual en porcentaje a tasa mensual.

    Args:
        annual_rate_pct: Tasa nominal anual en porcentaje, por ejemplo `12`.
            Admite `int` y `Decimal`.

    Returns:
        La tasa mensual expresada como fracción, por ejemplo
        `Decimal("0.01")` para una tasa anual del 12 %.

    Raises:
        TypeError: Si el tipo del valor no está admitido (`float`, `str` y
            `bool` incluidos).
        ValueError: Si la tasa es negativa, supera el 100 % o no es finita.
    """
    rate = _to_decimal(annual_rate_pct, "annual_rate_pct")

    if rate < 0 or rate > 100:
        raise ValueError(f"annual_rate_pct must be between 0 and 100, got {rate}")

    with localcontext() as context:
        context.prec = CALC_PRECISION
        return (rate / 100) / 12


def monthly_payment(principal: Number, annual_rate_pct: Number, months: int) -> Decimal:
    """Calcula la cuota fija de un préstamo con amortización francesa.

    La cuota responde a la fórmula `cuota = P * i / (1 - (1 + i) ** -n)`, donde
    `i` es la tasa mensual equivalente. Sin tasa, la cuota es el capital
    dividido por el plazo.

    Args:
        principal: Capital del préstamo, no negativo. Admite `int` y `Decimal`.
        annual_rate_pct: Tasa nominal anual en porcentaje. Admite `int` y
            `Decimal`.
        months: Cantidad de cuotas, entre 1 y 480.

    Returns:
        La cuota fija del préstamo con exactamente dos decimales. Un capital de
        `0` produce una cuota de `Decimal("0.00")`.

    Raises:
        TypeError: Si `principal` o `annual_rate_pct` tienen un tipo no
            admitido (`float`, `str` y `bool` incluidos), o si `months` no es
            un `int`.
        ValueError: Si el capital es negativo, la tasa está fuera de
            `[0, 100]` o el plazo está fuera de `[1, 480]`.
    """
    amount = _to_decimal(principal, "principal")
    rate = _to_decimal(annual_rate_pct, "annual_rate_pct")
    _validate_loan_inputs(amount, rate, months)

    rate_monthly = monthly_rate(rate)

    with localcontext() as context:
        context.prec = CALC_PRECISION
        if rate_monthly == 0:
            payment = amount / months
        else:
            growth = (1 + rate_monthly) ** (-months)
            payment = amount * rate_monthly / (1 - growth)
        return _sin_cero_negativo(payment.quantize(CENTS, rounding=ROUND_HALF_UP))


def amortization_schedule(
    principal: Number, annual_rate_pct: Number, months: int
) -> list[AmortizationRow]:
    """Genera el cronograma de amortización de un préstamo con cuota fija.

    Cada período calcula el interés sobre el saldo vigente y descuenta el
    capital amortizado. La última cuota absorbe el saldo remanente para que
    el balance final sea exactamente `Decimal("0.00")`.

    Args:
        principal: Capital del préstamo, no negativo. Admite `int` y `Decimal`.
        annual_rate_pct: Tasa nominal anual en porcentaje. Admite `int` y
            `Decimal`.
        months: Cantidad de cuotas, entre 1 y 480.

    Returns:
        Una lista con `months` diccionarios, cada uno con las claves
        `period`, `payment`, `interest`, `principal` y `balance`. Con un
        capital de `0` todas las filas valen `Decimal("0.00")`.

    Raises:
        TypeError: Si `principal` o `annual_rate_pct` tienen un tipo no
            admitido (`float`, `str` y `bool` incluidos), o si `months` no es
            un `int`.
        ValueError: Si el capital es negativo, la tasa está fuera de
            `[0, 100]` o el plazo está fuera de `[1, 480]`.
    """
    amount = _to_decimal(principal, "principal")
    rate = _to_decimal(annual_rate_pct, "annual_rate_pct")
    _validate_loan_inputs(amount, rate, months)

    rate_monthly = monthly_rate(rate)
    payment = monthly_payment(amount, rate, months)

    rows: list[AmortizationRow] = []
    balance = amount

    for period in range(1, months + 1):
        if rate_monthly == 0:
            interest = Decimal("0.00")
        else:
            interest = (balance * rate_monthly).quantize(CENTS, rounding=ROUND_HALF_UP)
        interest = _sin_cero_negativo(interest)

        if period == months:
            principal_part = balance.quantize(CENTS, rounding=ROUND_HALF_UP)
            row_payment = (principal_part + interest).quantize(CENTS, rounding=ROUND_HALF_UP)
            new_balance = Decimal("0.00")
        else:
            principal_part = (payment - interest).quantize(CENTS, rounding=ROUND_HALF_UP)
            row_payment = payment
            new_balance = (balance - principal_part).quantize(CENTS, rounding=ROUND_HALF_UP)

        rows.append(
            {
                "period": period,
                "payment": _sin_cero_negativo(row_payment),
                "interest": interest,
                "principal": _sin_cero_negativo(principal_part),
                "balance": _sin_cero_negativo(new_balance),
            }
        )
        balance = new_balance

    return rows
