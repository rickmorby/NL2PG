"""Introspezione AST del DDL: CREATE TABLE, colonne PK e FK.

:author: Riccardo Morabito
"""

from sqlglot import exp, parse
from sqlglot.errors import ParseError

MIN_COMPOSITE_FK = 2


def collect_pk_fk(create: exp.Create) -> tuple[set[str], set[str]]:
    """Raccoglie colonne PK e FK di una CREATE TABLE (livello colonna e tabella)."""
    pk_cols: set[str] = set()
    fk_cols: set[str] = set()
    for cd in create.find_all(exp.ColumnDef):
        for spec in cd.find_all(exp.ColumnConstraint):
            if isinstance(spec.kind, exp.PrimaryKeyColumnConstraint):
                pk_cols.add(cd.name.lower())
            if isinstance(spec.kind, exp.Reference):
                fk_cols.add(cd.name.lower())
    for cons in create.find_all(exp.PrimaryKey):
        pk_cols.update(
            e.name.lower() for e in cons.expressions if isinstance(e, (exp.Column, exp.Identifier))
        )
    for ft in create.find_all(exp.ForeignKey):
        fk_cols.update(
            e.name.lower() for e in ft.expressions if isinstance(e, (exp.Column, exp.Identifier))
        )
    return pk_cols, fk_cols


def get_all_creates(ddl: str) -> list[exp.Create]:
    """Estrae tutte le istruzioni CREATE TABLE dal DDL multi-statement."""
    try:
        trees = parse(ddl, read="postgres")
        creates = []
        for t in trees:
            if t:
                if isinstance(t, exp.Create):
                    creates.append(t)
                creates.extend(t.find_all(exp.Create))
        return list(dict.fromkeys(creates))
    except (ParseError, ValueError, AttributeError):
        return []
