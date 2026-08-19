"""Adattatore outbound per l'introspezione dello schema PostgreSQL da information_schema.

:author: Riccardo Morabito
"""

from bench.domain.models.data import ColumnSchema, SchemaModel, TableSchema


def introspect_schema(connection, schema_name: str) -> SchemaModel:
    """Costruisce il SchemaModel dalla sorgente autoritativa information_schema.

    :param connection: connessione psycopg aperta.
    :param schema_name: nome dello schema PostgreSQL da ispezionare.
    """
    columns = _fetch_columns(connection, schema_name)
    primary_keys = _fetch_primary_keys(connection, schema_name)
    foreign_keys = _fetch_foreign_keys(connection, schema_name)

    tables: dict[str, list[ColumnSchema]] = {}
    for row in columns:
        table_name, column_name, data_type, is_nullable = row
        column = ColumnSchema(
            name=column_name,
            data_type=data_type,
            nullable=is_nullable == "YES",
        )
        tables.setdefault(table_name, []).append(column)

    for table_name, column_name in primary_keys:
        for column in tables.get(table_name, []):
            if column.name == column_name:
                column.is_pk = True

    for child_table, child_column, parent_table, parent_column in foreign_keys:
        for column in tables.get(child_table, []):
            if column.name == child_column:
                column.is_fk = True
                column.fk_parent_table = parent_table
                column.fk_parent_column = parent_column

    return SchemaModel([TableSchema(name, cols) for name, cols in tables.items()])


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
