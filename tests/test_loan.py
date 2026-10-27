"""Pruebas de la librería de cálculo de préstamos con amortización francesa.

La suite cubre las tres funciones públicas de `loan`: la tasa mensual, la
cuota fija y el cronograma de amortización, incluyendo el redondeo
`ROUND_HALF_UP`, el ajuste de la última cuota y las validaciones de tipo y
rango (capital no negativo, tasa en `[0, 100]` y plazo entre 1 y 480 meses).
Todas las comparaciones se realizan con `Decimal` explícito y sin conexiones
de red ni servicios externos.
"""

from decimal import Decimal

import pytest

from loan import CENTS, amortization_schedule, monthly_payment, monthly_rate

CLAVES_ESPERADAS = ["period", "payment", "interest", "principal", "balance"]


# ---------------------------------------------------------------------------
# monthly_rate
# ---------------------------------------------------------------------------


def test_la_constante_cents_representa_un_centavo():
    assert CENTS == Decimal("0.01")


def test_la_tasa_mensual_de_12_por_ciento_es_el_1_por_ciento():
    assert monthly_rate(12) == Decimal("0.01")


def test_la_tasa_mensual_sin_interes_es_cero():
    assert monthly_rate(0) == Decimal("0")


def test_la_tasa_mensual_de_6_por_ciento_es_el_0_5_por_ciento():
    assert monthly_rate(6) == Decimal("0.005")


def test_la_tasa_mensual_se_devuelve_como_decimal():
    assert isinstance(monthly_rate(12), Decimal)


@pytest.mark.parametrize("tasa", [12, Decimal("12")])
def test_la_tasa_mensual_acepta_int_y_decimal(tasa):
    assert monthly_rate(tasa) == Decimal("0.01")


@pytest.mark.parametrize("tasa", [12.0, "12"])
def test_la_tasa_mensual_rechaza_float_y_str(tasa):
    with pytest.raises(TypeError):
        monthly_rate(tasa)


def test_la_tasa_mensual_rechaza_una_tasa_negativa():
    with pytest.raises(ValueError):
        monthly_rate(-1)


def test_la_tasa_mensual_rechaza_una_tasa_mayor_a_100():
    with pytest.raises(ValueError):
        monthly_rate(101)


@pytest.mark.parametrize("tasa", ["abc", "12", "NaN", "Infinity", float("nan")])
def test_la_tasa_mensual_rechaza_una_tasa_con_tipo_no_admitido(tasa):
    with pytest.raises(TypeError):
        monthly_rate(tasa)


@pytest.mark.parametrize(
    "tasa", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")]
)
def test_la_tasa_mensual_rechaza_una_tasa_no_finita(tasa):
    with pytest.raises(ValueError):
        monthly_rate(tasa)


@pytest.mark.parametrize("tasa", [True, False])
def test_la_tasa_mensual_rechaza_una_tasa_booleana(tasa):
    with pytest.raises(TypeError):
        monthly_rate(tasa)


# ---------------------------------------------------------------------------
# monthly_payment
# ---------------------------------------------------------------------------


def test_la_cuota_de_100000_al_12_por_ciento_a_12_meses_es_8884_88():
    assert monthly_payment(100000, 12, 12) == Decimal("8884.88")


def test_la_cuota_de_1000_al_12_por_ciento_a_12_meses_es_88_85():
    assert monthly_payment(1000, 12, 12) == Decimal("88.85")


def test_sin_tasa_la_cuota_es_el_capital_dividido_entre_el_plazo():
    assert monthly_payment(1200, 0, 12) == Decimal("100.00")


def test_sin_tasa_la_cuota_redondea_a_la_parte_decimal_mas_alza():
    assert monthly_payment(1000, 0, 3) == Decimal("333.33")


def test_la_cuota_tiene_exactamente_dos_decimales():
    assert monthly_payment(1000, 12, 12).as_tuple().exponent == -2


def test_la_cuota_es_un_multiplo_de_cents():
    assert monthly_payment(1000, 12, 12) % CENTS == 0


def test_la_cuota_acepta_entradas_decimal():
    assert monthly_payment(Decimal("1000"), Decimal("12"), 12) == Decimal("88.85")


@pytest.mark.parametrize("principal", [True, False])
def test_la_cuota_rechaza_un_capital_booleano(principal):
    with pytest.raises(TypeError):
        monthly_payment(principal, 12, 12)


@pytest.mark.parametrize("tasa", [True, False])
def test_la_cuota_rechaza_una_tasa_booleana(tasa):
    with pytest.raises(TypeError):
        monthly_payment(1000, tasa, 12)


@pytest.mark.parametrize("capital", [Decimal("1000")])
def test_la_cuota_acepta_el_capital_como_decimal(capital):
    assert monthly_payment(capital, 12, 12) == Decimal("88.85")


@pytest.mark.parametrize("tasa", [Decimal("12")])
def test_la_cuota_acepta_la_tasa_como_decimal(tasa):
    assert monthly_payment(1000, tasa, 12) == Decimal("88.85")


@pytest.mark.parametrize("capital", [1000.0, "1000"])
def test_la_cuota_rechaza_un_capital_con_tipo_no_admitido(capital):
    with pytest.raises(TypeError):
        monthly_payment(capital, 12, 12)


@pytest.mark.parametrize("tasa", [12.0, "12"])
def test_la_cuota_rechaza_una_tasa_con_tipo_no_admitido(tasa):
    with pytest.raises(TypeError):
        monthly_payment(1000, tasa, 12)


@pytest.mark.parametrize("capital", [None, [1000], {"capital": 1000}])
def test_la_cuota_rechaza_un_capital_de_tipo_no_numerico(capital):
    with pytest.raises(TypeError):
        monthly_payment(capital, 12, 12)


@pytest.mark.parametrize("tasa", [Decimal("NaN"), Decimal("Infinity")])
def test_la_cuota_rechaza_una_tasa_no_finita(tasa):
    with pytest.raises(ValueError):
        monthly_payment(1000, tasa, 12)


@pytest.mark.parametrize("meses", [12.0, "12", True])
def test_la_cuota_rechaza_un_plazo_que_no_es_entero(meses):
    with pytest.raises(TypeError):
        monthly_payment(1000, 12, meses)


@pytest.mark.parametrize("principal", [-1, -1000, Decimal("-1000.00"), Decimal("-0.01")])
def test_la_cuota_rechaza_un_capital_negativo(principal):
    with pytest.raises(ValueError):
        monthly_payment(principal, 12, 12)


@pytest.mark.parametrize("capital", [0, Decimal("0"), Decimal("0.00")])
def test_la_cuota_admite_un_capital_cero(capital):
    assert monthly_payment(capital, 12, 12) == Decimal("0.00")


def test_la_cuota_admite_un_capital_cero_sin_tasa():
    assert monthly_payment(0, 0, 12) == Decimal("0.00")


def test_la_cuota_de_un_capital_cero_no_produce_menos_cero():
    valor = monthly_payment(0, 12, 12)
    assert not (valor == 0 and valor.as_tuple().sign == 1)


@pytest.mark.parametrize("tasa", [-1, 101, Decimal("-0.01"), Decimal("100.01")])
def test_la_cuota_rechaza_una_tasa_fuera_de_rango(tasa):
    with pytest.raises(ValueError):
        monthly_payment(1000, tasa, 12)


@pytest.mark.parametrize("meses", [0, -1, 481, 1000])
def test_la_cuota_rechaza_un_plazo_fuera_de_rango(meses):
    with pytest.raises(ValueError):
        monthly_payment(1000, 12, meses)


# ---------------------------------------------------------------------------
# amortization_schedule
# ---------------------------------------------------------------------------


def test_el_cronograma_tiene_una_fila_por_periodo():
    assert len(amortization_schedule(1000, 12, 12)) == 12


def test_el_cronograma_expone_exactamente_las_claves_esperadas():
    for fila in amortization_schedule(1000, 12, 12):
        assert list(fila.keys()) == CLAVES_ESPERADAS
        assert set(fila.keys()) == set(CLAVES_ESPERADAS)


def test_el_cronograma_numera_los_periodos_de_forma_correlativa():
    filas = amortization_schedule(1000, 12, 12)
    assert [fila["period"] for fila in filas] == list(range(1, 13))


def test_la_primera_fila_del_cronograma_es_la_esperada():
    filas = amortization_schedule(1000, 12, 12)
    assert filas[0] == {
        "period": 1,
        "payment": Decimal("88.85"),
        "interest": Decimal("10.00"),
        "principal": Decimal("78.85"),
        "balance": Decimal("921.15"),
    }


def test_cada_cuota_se_descompone_en_interes_mas_capital():
    for fila in amortization_schedule(1000, 12, 12):
        assert fila["payment"] == fila["interest"] + fila["principal"]


def test_la_suma_del_capital_amortizado_iguala_al_capital_original():
    filas = amortization_schedule(1000, 12, 12)
    assert sum(fila["principal"] for fila in filas) == Decimal("1000.00")


def test_el_saldo_final_del_cronograma_es_exactamente_cero():
    filas = amortization_schedule(1000, 12, 12)
    assert filas[-1]["balance"] == Decimal("0.00")


def test_el_saldo_de_cada_periodo_es_el_anterior_menos_el_capital_amortizado():
    filas = amortization_schedule(1000, 12, 12)
    for anterior, actual in zip(filas, filas[1:]):
        assert actual["balance"] == anterior["balance"] - actual["principal"]


def test_la_ultima_cuota_amortiza_el_saldo_pendiente_completo():
    filas = amortization_schedule(1000, 12, 12)
    assert filas[-1]["principal"] == filas[-2]["balance"]
    assert filas[-1]["balance"] == Decimal("0.00")


def test_las_cuotas_intermedias_coinciden_con_la_cuota_fija():
    filas = amortization_schedule(1000, 12, 12)
    cuota = monthly_payment(1000, 12, 12)
    for fila in filas[:-1]:
        assert fila["payment"] == cuota


def test_el_cronograma_sin_tasa_tiene_intereses_en_cero():
    filas = amortization_schedule(1000, 0, 3)
    assert [fila["interest"] for fila in filas] == [
        Decimal("0.00"),
        Decimal("0.00"),
        Decimal("0.00"),
    ]


def test_el_cronograma_sin_tasa_ajusta_la_ultima_cuota_con_el_centavo_residual():
    filas = amortization_schedule(1000, 0, 3)
    assert [fila["payment"] for fila in filas] == [
        Decimal("333.33"),
        Decimal("333.33"),
        Decimal("333.34"),
    ]
    assert filas[-1]["balance"] == Decimal("0.00")


def test_el_cronograma_de_100000_al_12_por_ciento_termina_saldo_en_cero():
    filas = amortization_schedule(100000, 12, 12)
    assert len(filas) == 12
    assert sum(fila["principal"] for fila in filas) == Decimal("100000.00")
    assert filas[-1]["balance"] == Decimal("0.00")


def test_los_importes_del_cronograma_son_decimal_con_dos_decimales():
    for fila in amortization_schedule(1000, 12, 12):
        for clave in ("payment", "interest", "principal", "balance"):
            assert isinstance(fila[clave], Decimal)
            assert fila[clave].as_tuple().exponent == -2


def test_el_cronograma_no_produce_importes_negativos():
    for fila in amortization_schedule(1000, 12, 12):
        for clave in ("payment", "interest", "principal", "balance"):
            assert fila[clave] >= 0


def test_el_cronograma_no_produce_ceros_con_signo_negativo():
    for fila in amortization_schedule(1000, 12, 12):
        for clave in ("payment", "interest", "principal", "balance"):
            valor = fila[clave]
            assert not (valor == 0 and valor.as_tuple().sign == 1)


@pytest.mark.parametrize("capital", [True, False])
def test_el_cronograma_rechaza_un_capital_booleano(capital):
    with pytest.raises(TypeError):
        amortization_schedule(capital, 12, 12)


@pytest.mark.parametrize("tasa", [True, False])
def test_el_cronograma_rechaza_una_tasa_booleana(tasa):
    with pytest.raises(TypeError):
        amortization_schedule(1000, tasa, 12)


@pytest.mark.parametrize("capital", [Decimal("1000")])
def test_el_cronograma_acepta_el_capital_como_decimal(capital):
    filas = amortization_schedule(capital, 12, 12)
    assert filas[0] == {
        "period": 1,
        "payment": Decimal("88.85"),
        "interest": Decimal("10.00"),
        "principal": Decimal("78.85"),
        "balance": Decimal("921.15"),
    }
    assert sum(fila["principal"] for fila in filas) == Decimal("1000.00")
    assert filas[-1]["balance"] == Decimal("0.00")


@pytest.mark.parametrize("capital", [1000.0, "1000"])
def test_el_cronograma_rechaza_un_capital_con_tipo_no_admitido(capital):
    with pytest.raises(TypeError):
        amortization_schedule(capital, 12, 12)


@pytest.mark.parametrize("tasa", [12.0, "12"])
def test_el_cronograma_rechaza_una_tasa_con_tipo_no_admitido(tasa):
    with pytest.raises(TypeError):
        amortization_schedule(1000, tasa, 12)


@pytest.mark.parametrize("meses", [12.0, "12", True])
def test_el_cronograma_rechaza_un_plazo_que_no_es_entero(meses):
    with pytest.raises(TypeError):
        amortization_schedule(1000, 12, meses)


@pytest.mark.parametrize("principal", [-1, -1000, Decimal("-1000.00"), Decimal("-0.01")])
def test_el_cronograma_rechaza_un_capital_negativo(principal):
    with pytest.raises(ValueError):
        amortization_schedule(principal, 12, 12)


@pytest.mark.parametrize("capital", [0, Decimal("0"), Decimal("0.00")])
def test_el_cronograma_admite_un_capital_cero(capital):
    filas = amortization_schedule(capital, 12, 12)
    assert len(filas) == 12
    for fila in filas:
        assert fila["payment"] == Decimal("0.00")
        assert fila["interest"] == Decimal("0.00")
        assert fila["principal"] == Decimal("0.00")
        assert fila["balance"] == Decimal("0.00")
    assert sum(fila["principal"] for fila in filas) == Decimal("0.00")
    assert filas[-1]["balance"] == Decimal("0.00")


def test_el_cronograma_de_un_capital_cero_no_produce_menos_cero():
    for fila in amortization_schedule(0, 12, 12):
        for clave in ("payment", "interest", "principal", "balance"):
            valor = fila[clave]
            assert not (valor == 0 and valor.as_tuple().sign == 1)


@pytest.mark.parametrize("tasa", [-1, 101, Decimal("-0.01"), Decimal("100.01")])
def test_el_cronograma_rechaza_una_tasa_fuera_de_rango(tasa):
    with pytest.raises(ValueError):
        amortization_schedule(1000, tasa, 12)


@pytest.mark.parametrize("meses", [0, -1, 481, 1000])
def test_el_cronograma_rechaza_un_plazo_fuera_de_rango(meses):
    with pytest.raises(ValueError):
        amortization_schedule(1000, 12, meses)


# ---------------------------------------------------------------------------
# Contrato de fallos explícitos (tipos no admitidos y rangos inválidos)
# ---------------------------------------------------------------------------

FUNCIONES_DE_PRESTAMO = (monthly_payment, amortization_schedule)


@pytest.mark.parametrize("funcion", FUNCIONES_DE_PRESTAMO)
@pytest.mark.parametrize("capital", [1000.0, True])
def test_el_capital_con_tipo_no_admitido_falla_con_type_error(funcion, capital):
    with pytest.raises(TypeError):
        funcion(capital, 12, 12)


@pytest.mark.parametrize("funcion", FUNCIONES_DE_PRESTAMO)
@pytest.mark.parametrize("tasa", [12.0, True])
def test_la_tasa_con_tipo_no_admitido_falla_con_type_error(funcion, tasa):
    with pytest.raises(TypeError):
        funcion(1000, tasa, 12)


@pytest.mark.parametrize("funcion", FUNCIONES_DE_PRESTAMO)
@pytest.mark.parametrize("meses", [12.0, True, "12"])
def test_un_plazo_que_no_es_entero_falla_con_type_error(funcion, meses):
    with pytest.raises(TypeError):
        funcion(1000, 12, meses)


@pytest.mark.parametrize("funcion", FUNCIONES_DE_PRESTAMO)
@pytest.mark.parametrize("capital", [-1, -1000])
def test_un_capital_negativo_falla_con_value_error(funcion, capital):
    with pytest.raises(ValueError):
        funcion(capital, 12, 12)


@pytest.mark.parametrize("funcion", FUNCIONES_DE_PRESTAMO)
def test_un_capital_cero_no_es_una_entrada_invalida(funcion):
    resultado = funcion(0, 12, 12)
    if isinstance(resultado, list):
        assert resultado[-1]["balance"] == Decimal("0.00")
    else:
        assert resultado == Decimal("0.00")


@pytest.mark.parametrize("funcion", FUNCIONES_DE_PRESTAMO)
@pytest.mark.parametrize("tasa", [-1, 101])
def test_una_tasa_fuera_de_rango_falla_con_value_error(funcion, tasa):
    with pytest.raises(ValueError):
        funcion(1000, tasa, 12)


@pytest.mark.parametrize("funcion", FUNCIONES_DE_PRESTAMO)
@pytest.mark.parametrize("meses", [0, -1, 481])
def test_un_plazo_fuera_de_rango_falla_con_value_error(funcion, meses):
    with pytest.raises(ValueError):
        funcion(1000, 12, meses)
