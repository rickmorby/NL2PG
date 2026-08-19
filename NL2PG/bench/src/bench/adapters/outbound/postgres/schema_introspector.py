"""Adattatore outbound per l'introspezione dello schema PostgreSQL da information_schema.

:author: Riccardo Morabito
"""

from collections import defaultdict

from bench.domain.models.data import ColumnSchema, SchemaModel, TableSchema


def introspect_schema(connection, schema_name: str) -> SchemaModel:
    """Costruisce il SchemaModel dalla sorgente autoritativa information_schema.

    :param connection: connessione psycopg aperta.
    :param schema_name: nome dello schema PostgreSQL da ispezionare.
    """
    columns = _fetch_columns(connection, schema_name)
    primary_keys = _fetch_primary_keys(connection, schema_name)
    foreign_keys = _fetch_foreign_keys(connection, schema_name)
    unique_constraints = _fetch_unique_constraints(connection, schema_name)

    tables: dict[str, list[ColumnSchema]] = {}
    for row in columns:
        table_name, column_name, data_type, is_nullable = row
        column = ColumnSchema(
            name=column_name,
            data_type=data_type,
            nullable=is_nullable == "YES",
        )
        tables.setdefault(table_name, []).append(column)

    _apply_primary_keys(tables, primary_keys)
    _apply_foreign_keys(tables, foreign_keys)
    unique_groups = _apply_unique_constraints(tables, unique_constraints)

    return SchemaModel(
        [TableSchema(name, cols, unique_groups.get(name)) for name, cols in tables.items()]
    )


def _apply_primary_keys(tables: dict[str, list[ColumnSchema]], primary_keys: list[tuple]) -> None:
    """Marca le colonne PK nelle tabelle."""
    for table_name, column_name in primary_keys:
        for column in tables.get(table_name, []):
            if column.name == column_name:
                column.is_pk = True


def _apply_foreign_keys(tables: dict[str, list[ColumnSchema]], foreign_keys: list[tuple]) -> None:
    """Marca le colonne FK e associa tabella/colonna padre."""
    for child_table, child_column, parent_table, parent_column in foreign_keys:
        for column in tables.get(child_table, []):
            if column.name == child_column:
                column.is_fk = True
                column.fk_parent_table = parent_table
                column.fk_parent_column = parent_column


def _apply_unique_constraints(
    tables: dict[str, list[ColumnSchema]],
    unique_constraints: list[tuple[str, list[str]]],
) -> dict[str, list[list[str]]]:
    """Marca le colonne UNIQUE e restituisce i gruppi per tabella."""
    groups: dict[str, list[list[str]]] = defaultdict(list)
    for table_name, group_columns in unique_constraints:
        groups[table_name].append(group_columns)
        for col_name in group_columns:
            for column in tables.get(table_name, []):
                if column.name == col_name:
                    column.is_unique = True
    return dict(groups)


def _fetch_columns(connection, schema_name: str) -> list[tuple]:
    """Restituisce colonne, tipi e nullabilita' delle tabelle dello schema."""
    query = (
        "SELECT table_name, column_name, data_type, is_nullable "
        "FROM information_schema.columns "
        "WHERE table_schema = %s ORDER BY table_name, ordinal_position"
    )
    return connection.execute(query, (schema_name,)).fetchall()


def _fetch_primary_keys(connection, schema_name: str) -> list[tuple]:
    """Restituisce le coppie (tabella, colonna) delle chiavi primarie."""
    query = (
        "SELECT tc.table_name, kcu.column_name "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "ON tc.constraint_name = kcu.constraint_name "
        "AND tc.table_schema = kcu.table_schema "
        "WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = %s"
    )
    return connection.execute(query, (schema_name,)).fetchall()


def _fetch_foreign_keys(connection, schema_name: str) -> list[tuple]:
    """Restituisce le tuple (tabella figlia, colonna, tabella padre, colonna padre)."""
    query = (
        "SELECT tc.table_name, kcu.column_name, ccu.table_name, ccu.column_name "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "ON tc.constraint_name = kcu.constraint_name "
        "AND tc.table_schema = kcu.table_schema "
        "JOIN information_schema.constraint_column_usage ccu "
        "ON tc.constraint_name = ccu.constraint_name "
        "AND tc.table_schema = ccu.table_schema "
        "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s"
    )
    return connection.execute(query, (schema_name,)).fetchall()


def _fetch_unique_constraints(connection, schema_name: str) -> list[tuple[str, list[str]]]:
    """Restituisce le coppie (tabella, [colonne]) per ogni vincolo UNIQUE.

    Raggruppa per ``constraint_name`` cosi' da catturare sia vincoli
    mono-colonna sia compositi.
    """
    query = (
        "SELECT tc.table_name, tc.constraint_name, kcu.column_name "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "ON tc.constraint_name = kcu.constraint_name "
        "AND tc.table_schema = kcu.table_schema "
        "WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = %s "
        "ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position"
    )
    rows = connection.execute(query, (schema_name,)).fetchall()
    groups: dict[tuple[str, str], list[str]] = {}
    for table_name, constraint_name, column_name in rows:
        groups.setdefault((table_name, constraint_name), []).append(column_name)
    return [(table, cols) for (table, _), cols in groups.items()]
