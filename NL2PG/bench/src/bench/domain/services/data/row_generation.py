"""Generazione delle righe per tabella: espansione template e rumore.

Due responsabilita' separate: ``RowExpander`` orchestra l'espansione dei
template canonici per tabella (loop, duplicati, PK composite, UNIQUE),
``RowBuilder`` costruisce una singola riga applicando variazioni, PK e valori
UNIQUE univoci e rumore controllato (NULL, outlier). I volumi sono calcolati
da ``RowCounter``.

:author: Riccardo Morabito
"""

import re
from contextlib import suppress
from random import Random
from typing import Any, ClassVar

from bench.domain.models.data import (
    ColumnSchema,
    ColumnVariationDTO,
    DataSpecDTO,
    SchemaModel,
    TableDataSpecDTO,
    TableSchema,
)
from bench.domain.services.data.column_types import (
    is_date_type,
    is_integer_type,
    neutral_value,
    scale_value,
    shift_value,
)

_OUTLIER_COIN_FLIP = 0.5
_CF_LENGTH = 16
_ALPHABET_SIZE = 26
_MAX_SUFFIX_ATTEMPTS = 100
_RE_CHECK_REGEX = re.compile(r"~\*?\s*'([^']+)'")
_RE_CHECK_LENGTH = re.compile(r"length\s*\(\s*\w+\s*\)\s*([<>]=?|=)\s*(\d+)", re.I)


def _check_regex_part(value: str, part: str) -> bool | None:
    """Valida regex se presente, altrimenti None."""
    m = _RE_CHECK_REGEX.search(part)
    if not m:
        return None
    pat = m.group(1)
    try:
        return bool(re.search(pat, value))
    except re.error:
        return True


def _check_length_part(value: str, part: str) -> bool | None:
    """Valida length se presente, altrimenti None."""
    ml = _RE_CHECK_LENGTH.search(part)
    if not ml:
        return None
    op, num = ml.group(1), int(ml.group(2))
    lv = len(value)
    checks = {
        ">=": lv >= num,
        ">": lv > num,
        "<=": lv <= num,
        "<": lv < num,
        "=": lv == num,
    }
    return checks.get(op, True)


_RE_CHECK_BETWEEN = re.compile(
    r"(?:VALUE|[a-zA-Z0-9_]+)\s+BETWEEN\s+(-?\d+(?:\.\d+)?)\s+AND\s+(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_RE_CHECK_CMP = re.compile(
    r"(?:VALUE|[a-zA-Z0-9_]+)\s*(>=|<=|>|<|=)\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE
)
_RE_CHECK_IN = re.compile(r"(?:VALUE|[a-zA-Z0-9_]+)\s+IN\s*\(([^)]+)\)", re.IGNORECASE)


def _check_numeric_parts(val_num: float, check_expr: str) -> bool:
    """Valida vincoli BETWEEN e di confronto numerico."""
    for m in _RE_CHECK_BETWEEN.finditer(check_expr):
        low, high = float(m.group(1)), float(m.group(2))
        if not (low <= val_num <= high):
            return False
    clean_check = _RE_CHECK_BETWEEN.sub("", check_expr)
    for m in _RE_CHECK_CMP.finditer(clean_check):
        op, limit = m.group(1), float(m.group(2))
        if (
            (op == ">=" and val_num < limit)
            or (op == ">" and val_num <= limit)
            or (op == "<=" and val_num > limit)
            or (op == "<" and val_num >= limit)
            or (op == "=" and val_num != limit)
        ):
            return False
    return True


def _satisfies_check(value: str, check_expr: str | None) -> bool:
    """Valida value contro CHECK di colonna (regex, length, between, cmp, in)."""
    if not check_expr or value is None:
        return True
    val_str = str(value).strip("'")
    val_num = None
    with suppress(ValueError, TypeError):
        val_num = float(val_str)

    if val_num is not None and not _check_numeric_parts(val_num, check_expr):
        return False

    for m in _RE_CHECK_IN.finditer(check_expr):
        allowed = [x.strip().strip("'\"") for x in m.group(1).split(",")]
        if val_str not in allowed:
            return False

    for raw_part in check_expr.split(" AND "):
        part = raw_part.strip()
        res = _check_regex_part(val_str, part)
        if res is not None:
            if not res:
                return False
            continue
        res = _check_length_part(val_str, part)
        if res is not None and not res:
            return False
    return True


def _unique_email(base: str, idx: int, max_len: int | None) -> str:
    """Variante email: local+idx@domain."""
    local, domain = base.split("@", 1)
    cand = f"{local}{idx}@{domain}"
    if max_len is not None and len(cand) > max_len:
        max_local = max_len - len(f"{idx}@{domain}")
        local = local[: max(1, max_local)]
        cand = f"{local}{idx}@{domain}"
    return cand


def _unique_cf(base: str, idx: int, max_len: int | None) -> str:
    """Variante codice fiscale."""
    if idx < _ALPHABET_SIZE:
        cand = base[: _CF_LENGTH - 1] + chr(ord("A") + idx)
    else:
        try:
            serial = int(base[12:15])
        except ValueError:
            serial = 0
        new_serial = (serial + idx) % 1000
        last = chr(ord("A") + (idx % _ALPHABET_SIZE))
        cand = f"{base[:12]}{new_serial:03d}{last}"
    if max_len is not None and len(cand) > max_len:
        cand = cand[:max_len]
    return cand


def _unique_string(base: str, idx: int, max_len: int | None) -> str:
    """Genera stringa unica (email/CF/generico) senza validazione CHECK."""
    if idx == 0:
        return base
    if "@" in base:
        return _unique_email(base, idx, max_len)
    if len(base) == _CF_LENGTH and base[:6].isalpha() and base[:6].isupper():
        return _unique_cf(base, idx, max_len)
    cand = f"{base}{idx}"
    if max_len is not None and len(cand) > max_len:
        max_base = max_len - len(str(idx))
        cand = f"{base[: max(1, max_base)]}{idx}"
    if base.isdigit():
        try:
            cand2 = str(int(base) + idx).zfill(len(base))
            if (max_len is None or len(cand2) <= max_len) and len(cand2) < len(cand):
                return cand2
        except ValueError:
            pass
    return cand


def _generate_unique(
    column: ColumnSchema, template_value: Any, instance_index: int, used: set[Any]
) -> Any:
    """Genera valore univoco dal template (int/data/string)."""
    if is_integer_type(column.data_type):
        base = template_value if isinstance(template_value, int) else 1
        candidate = base + instance_index
        while candidate in used:
            candidate += 1
    elif is_date_type(column.data_type) and isinstance(template_value, str):
        candidate = shift_value(template_value, column, instance_index)
        suffix = 1
        while candidate in used:
            candidate = shift_value(template_value, column, instance_index + suffix)
            suffix += 1
    else:
        base = template_value if template_value is not None else column.name
        base_str = str(base)
        check = getattr(column, "check_expr", None)
        candidate = (
            base_str
            if instance_index == 0
            else _unique_string(base_str, instance_index, column.max_length)
        )
        suffix = 1
        while candidate in used or not _satisfies_check(candidate, check):
            candidate = _unique_string(base_str, instance_index + suffix, column.max_length)
            suffix += 1
            if suffix > _MAX_SUFFIX_ATTEMPTS:
                candidate = f"{base_str}_{instance_index + suffix}"
                break
    used.add(candidate)
    return candidate


class RowExpander:
    """Espande i template canonici in righe per tabella (loop e PK composite)."""

    def __init__(
        self, null_rate: float = 0.05, dup_rate: float = 0.03, outlier_rate: float = 0.02
    ) -> None:
        """Inietta i tassi di rumore e delega la riga singola al RowBuilder."""
        self._dup_rate = dup_rate
        self._builder = RowBuilder(null_rate, dup_rate, outlier_rate)

    def expand(
        self,
        spec: DataSpecDTO,
        schema: SchemaModel,
        counts: dict[str, int],
        rng: Random,
    ) -> dict[str, list[dict[str, Any]]]:
        """Genera le righe di ogni tabella espandendo i template lungo gli assi."""
        rows: dict[str, list[dict[str, Any]]] = {}
        for table_spec in spec.tables:
            table = schema.table(table_spec.table)
            count = counts[table.name.lower()]
            rows[table.name.lower()] = self._expand_table(table_spec, table, count, rng)
        return rows

    def _expand_table(
        self,
        table_spec: TableDataSpecDTO,
        table: TableSchema,
        count: int,
        rng: Random,
    ) -> list[dict[str, Any]]:
        """Genera le righe di una singola tabella da template, variazioni e rumore."""
        result: list[dict[str, Any]] = []
        templates = table_spec.templates
        base = count // len(templates)
        remainder = count % len(templates)
        used_pk: dict[str, set[Any]] = {col: set() for col in table.pk_columns}
        used_unique: dict[str, set[Any]] = {
            col.name: set()
            for col in table.columns
            if col.is_unique and not col.is_pk and not col.is_fk
        }
        used_composite: set[tuple] = set()
        used_composite_unique: dict[tuple[str, ...], set[tuple]] = {
            tuple(group): set() for group in table.unique_groups if len(group) > 1
        }
        for template_index, template in enumerate(templates):
            instances = base + (1 if template_index < remainder else 0)
            for instance_index in range(instances):
                duplicate = rng.random() < self._dup_rate and bool(result)
                row = self._builder.build(
                    table_spec,
                    table,
                    template,
                    instance_index,
                    used_pk,
                    used_unique,
                    rng,
                    duplicate,
                )
                if len(table.pk_columns) > 1:
                    self._ensure_composite_unique(table, row, used_composite)
                for group_key, used_set in used_composite_unique.items():
                    self._ensure_composite_unique_group(table, row, list(group_key), used_set)
                result.append(row)
        return result

    @staticmethod
    def _ensure_composite_unique(
        table: TableSchema, row: dict[str, Any], used_composite: set[tuple]
    ) -> None:
        """Rende unica la PK composite incrementando l'ultima colonna in caso di collisione."""
        composite_key = tuple(row[col] for col in table.pk_columns)
        suffix = 1
        while composite_key in used_composite:
            pk_col = table.pk_columns[-1]
            if is_integer_type(table.column(pk_col).data_type):
                row[pk_col] = int(row[pk_col]) + suffix
            suffix += 1
            composite_key = tuple(row[col] for col in table.pk_columns)
        used_composite.add(composite_key)

    @staticmethod
    def _ensure_composite_unique_group(
        table: TableSchema,
        row: dict[str, Any],
        group: list[str],
        used: set[tuple],
    ) -> None:
        """Rende unica una combinazione UNIQUE composita."""
        key = tuple(row[col] for col in group)
        suffix = 1
        while True:
            col_schema = table.column(group[-1])
            check = getattr(col_schema, "check_expr", None) if col_schema else None
            val_ok = _satisfies_check(str(row[group[-1]]), check) if col_schema else True
            if key not in used and val_ok:
                break
            last_col = group[-1]
            if col_schema and is_integer_type(col_schema.data_type):
                row[last_col] = int(row[last_col]) + suffix
            elif col_schema and is_date_type(col_schema.data_type):
                row[last_col] = shift_value(row[last_col], col_schema, suffix)
            else:
                val = str(row[last_col])
                row[last_col] = _unique_string(
                    val, suffix, col_schema.max_length if col_schema else None, check
                )
            suffix += 1
            key = tuple(row[col] for col in group)
            if suffix > _MAX_SUFFIX_ATTEMPTS:
                break
        used.add(key)


class RowBuilder:
    """Costruisce una singola riga: PK e UNIQUE univoche, variazioni e rumore controllato."""

    def __init__(
        self, null_rate: float = 0.05, dup_rate: float = 0.03, outlier_rate: float = 0.02
    ) -> None:
        """Inietta i tassi di rumore applicati alla riga."""
        self.null_rate = null_rate
        self.dup_rate = dup_rate
        self._outlier_rate = outlier_rate

    def build(
        self,
        table_spec: TableDataSpecDTO,
        table: TableSchema,
        template: dict[str, Any],
        instance_index: int,
        used_pk: dict[str, set[Any]],
        used_unique: dict[str, set[Any]],
        rng: Random,
        duplicate: bool,
    ) -> dict[str, Any]:
        """Costruisce una riga applicando variazioni, PK/UNIQUE uniche, NULL e outlier."""
        row: dict[str, Any] = {}
        for column in table.columns:
            variation = table_spec.variations.get(column.name)
            template_value = template.get(column.name)
            self._set_column_value(
                table,
                column,
                template_value,
                variation,
                instance_index,
                used_pk,
                used_unique,
                rng,
                duplicate,
                row,
            )
            self._inject_noise(column, variation, template_value, row, rng)
        for column in table.columns:
            if row[column.name] is None and not column.nullable and not column.is_pk:
                row[column.name] = neutral_value(column)
        self._enforce_temporal_ordering(row)
        return row

    _DATE_PAIRS: ClassVar[list[tuple[str, str]]] = [
        ("data_inizio", "data_fine"),
        ("data_decorrenza", "data_scadenza"),
        ("data_ammissione", "data_dimissione"),
        ("data_ordine", "data_consegna"),
        ("data_ordine", "data_spedizione"),
        ("data_spedizione", "data_consegna"),
        ("data_partenza", "data_consegna"),
        ("data_partenza", "data_arrivo"),
        ("data_evento", "data_denuncia"),
        ("data_attivazione", "data_scadenza"),
        ("data_apertura", "data_chiusura"),
        ("ora_inizio", "ora_fine"),
        ("data_assunzione", "data_dimissione"),
        ("data_assunzione", "data_fine"),
        ("valid_from", "valid_to"),
    ]

    @classmethod
    def _enforce_temporal_ordering(cls, row: dict[str, Any]) -> None:
        """Garantisce la coerenza temporale tra date di inizio e fine nella stessa riga."""
        for start_key, end_key in cls._DATE_PAIRS:
            if start_key in row and end_key in row:
                s_val, e_val = row[start_key], row[end_key]
                if s_val is not None and e_val is not None and str(e_val) < str(s_val):
                    row[start_key], row[end_key] = e_val, s_val

    def _set_column_value(
        self,
        table: TableSchema,
        column: ColumnSchema,
        template_value: Any,
        variation: ColumnVariationDTO | None,
        instance_index: int,
        used_pk: dict[str, set[Any]],
        used_unique: dict[str, set[Any]],
        rng: Random,
        duplicate: bool,
        row: dict[str, Any],
    ) -> None:
        """Assegna il valore della colonna: PK, UNIQUE, FK/duplicato, variazione o template."""
        is_secondary_pk = (
            column.is_pk and len(table.pk_columns) > 1 and column.name != table.pk_columns[0]
        )
        if column.is_pk and not is_secondary_pk:
            row[column.name] = self._unique_pk_value(
                column, template_value, instance_index, used_pk[column.name]
            )
        elif column.is_unique and not column.is_fk and column.name in used_unique:
            row[column.name] = self._unique_value(
                column, template_value, instance_index, used_unique[column.name]
            )
        elif column.is_fk or duplicate or is_secondary_pk:
            if is_secondary_pk and variation is not None and variation.axis != "fixed":
                val = self._vary_value(column, template_value, variation, rng)
                check = getattr(column, "check_expr", None)
                if check and not _satisfies_check(str(val), check):
                    val = template_value
                row[column.name] = val
            else:
                row[column.name] = template_value
        elif variation is not None and variation.axis != "fixed":
            val = self._vary_value(column, template_value, variation, rng)
            check = getattr(column, "check_expr", None)
            if check and not _satisfies_check(str(val), check):
                val = template_value
            row[column.name] = val
        else:
            row[column.name] = template_value

    def _inject_noise(
        self,
        column: ColumnSchema,
        variation: ColumnVariationDTO | None,
        template_value: Any,
        row: dict[str, Any],
        rng: Random,
    ) -> None:
        """Inietta NULL (colonne nullable) e outlier entro i limiti dichiarati."""
        if not column.is_pk and column.nullable and rng.random() < self.null_rate:
            row[column.name] = None
        if (
            not column.is_pk
            and not column.is_fk
            and variation is not None
            and variation.axis in ("shift", "scale")
            and row[column.name] is not None
            and rng.random() < self._outlier_rate
        ):
            outlier = self._outlier_value(column, template_value, variation, rng)
            check = getattr(column, "check_expr", None)
            if not check or _satisfies_check(str(outlier), check):
                row[column.name] = outlier

    @staticmethod
    def _unique_pk_value(
        column: ColumnSchema, template_value: Any, instance_index: int, used: set[Any]
    ) -> Any:
        """Genera un valore PK univoco partendo dal template (sequenziale per int)."""
        return _generate_unique(column, template_value, instance_index, used)

    @staticmethod
    def _unique_value(
        column: ColumnSchema, template_value: Any, instance_index: int, used: set[Any]
    ) -> Any:
        """Genera un valore UNIQUE univoco partendo dal template."""
        return _generate_unique(column, template_value, instance_index, used)

    @staticmethod
    def _vary_value(
        column: ColumnSchema, template_value: Any, variation: ColumnVariationDTO, rng: Random
    ) -> Any:
        """Applica l'asse di variazione dichiarato al valore del template."""
        if template_value is None:
            return None
        if variation.axis == "pool":
            return rng.choice(variation.pool)
        if variation.axis == "shift":
            delta = rng.uniform(variation.delta_min or 0, variation.delta_max or 0)
            return shift_value(template_value, column, delta)
        if variation.axis == "scale":
            factor = rng.uniform(variation.factor_min or 1, variation.factor_max or 1)
            return scale_value(template_value, factor)
        return template_value

    @staticmethod
    def _outlier_value(
        column: ColumnSchema, template_value: Any, variation: ColumnVariationDTO, rng: Random
    ) -> Any:
        """Valore estremo" entro i confini dichiarati (per domande max/min sensate)."""
        if variation.axis == "shift":
            extreme = (
                variation.delta_max if rng.random() < _OUTLIER_COIN_FLIP else variation.delta_min
            )
            return shift_value(template_value, column, extreme or 0)
        if variation.axis == "scale":
            extreme = (
                variation.factor_max if rng.random() < _OUTLIER_COIN_FLIP else variation.factor_min
            )
            return scale_value(template_value, extreme or 1)
        return template_value
