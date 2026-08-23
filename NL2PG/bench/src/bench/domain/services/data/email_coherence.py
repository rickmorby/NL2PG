"""Coerenza anagrafica dell'email: l'indirizzo e' una funzione di nome e cognome.

Un email non e' un asse di variazione indipendente ma deriva dall'anagrafica della
riga; la parte locale e' ricostruita da nome/cognome conservando il dominio, con
discriminante d'istanza per colonne UNIQUE o su collisione.

:author: Riccardo Morabito
"""

from re import IGNORECASE
from re import compile as re_compile
from re import sub

from bench.domain.models.data import TableSchema

_EMAIL_TOKEN = re_compile(r"email", IGNORECASE)


def _slug_person(value: str) -> str:
    """Riduce nome/cognome a token alfanumerico minuscolo per l'indirizzo email."""
    return sub(r"[^a-z0-9]+", "", value.lower())


def enforce_email_coherence(
    row: dict[str, object],
    table: TableSchema,
    instance_index: int,
    used_unique: dict[str, set[object]],
) -> None:
    """Riscrive l'email della riga coerentemente con nome/cognome presenti.

    Non altera righe prive di colonna email, di anagrafica o con email malformata;
    il dominio esistente e' conservato e max_length e' rispettato.
    """
    email_col = next((c for c in table.columns if _EMAIL_TOKEN.search(c.name)), None)
    if email_col is None:
        return
    current = row.get(email_col.name)
    if not isinstance(current, str) or "@" not in current:
        return
    nome = row.get("nome")
    cognome = row.get("cognome")
    if not isinstance(nome, str) or not isinstance(cognome, str):
        return
    local_slug = f"{_slug_person(nome)}.{_slug_person(cognome)}"
    if not local_slug.strip("."):
        return
    domain = current.split("@", 1)[1] or "example.com"
    new_local = f"{local_slug}{instance_index}" if email_col.is_unique else local_slug
    candidate = f"{new_local}@{domain}"
    if email_col.max_length is not None and len(candidate) > email_col.max_length:
        keep = max(1, email_col.max_length - len(f"@{domain}"))
        candidate = f"{new_local[:keep]}@{domain}"
    used = used_unique.setdefault(email_col.name, set())
    if candidate in used and not email_col.is_unique:
        candidate = f"{new_local}{instance_index}@{domain}"
        if email_col.max_length is not None and len(candidate) > email_col.max_length:
            keep = max(1, email_col.max_length - len(f"@{domain}"))
            candidate = f"{new_local[:keep]}{instance_index}@{domain}"
    row[email_col.name] = candidate
    used.add(candidate)
