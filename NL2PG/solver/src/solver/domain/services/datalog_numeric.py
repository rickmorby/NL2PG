"""Convenzione numerica condivisa tra fatti, traduttore e comparatore Datalog.

Clingo 5 esegue l'aritmetica di ground a 32 bit: la scala di rappresentazione
deve quindi essere scelta dai dati in modo che somme e prodotti restino entro
``_SAFE_BOUND``. La scala e' una potenza di 10 in ``[1, 1000]``: 1000 conserva
le tre cifre decimali presenti nel benchmark; scale inferiori si usano solo
quando i valori sono grandi, accettando la perdita di precisione decimale
(il chiamante devia al fallback LLM se serve precisione sottocentnesimo).

:author: Riccardo Morabito
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

DEFAULT_SCALE = 1000
MIN_PRECISE_SCALE = 100
_SAFE_BOUND = 1 << 30
_SCALES = (1000, 100, 10, 1)
_SCALE_DECIMAL = Decimal(DEFAULT_SCALE)


def scale_number(value: str | int | float | Decimal, scale: int = DEFAULT_SCALE) -> int:
    """Converte un valore SQL numerico nell'intero Clingo alla scala data."""
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Valore numerico non convertibile: {value!r}") from exc
    scaled = decimal_value * Decimal(scale)
    return int(scaled.to_integral_value(rounding=ROUND_HALF_UP))


def scale_sql_number(text: str, scale: int = DEFAULT_SCALE) -> str:
    """Restituisce il valore SQL numerico come costante intera Clingo."""
    return str(scale_number(text, scale))


def unscale_number(value: int | float | Decimal, scale: int = DEFAULT_SCALE) -> float:
    """Converte un intero Clingo scalato nel valore numerico SQL corrispondente."""
    return float(Decimal(str(value)) / Decimal(scale))


def choose_scale(max_abs_value: Decimal, row_count: int) -> int:
    """Sceglie la scala massima che mantiene somme e confronti entro il limite.

    Il vincolo copre il caso peggiore di ``#sum`` (tutte le righe al valore
    massimo) e lascia margine per gli intermedi dell'aritmetica di ground.
    """
    rows = max(int(row_count), 1)
    for scale in _SCALES:
        worst_case = abs(max_abs_value) * scale * rows
        if worst_case < _SAFE_BOUND:
            return scale
    return 1
