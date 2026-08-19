"""Builder puro delle proiezioni ruolo->campi per gli esempi few-shot.

Fonte unica di verità su cosa ogni ruolo generativo deve imitare: gli esempi
promossi contengono SOLO i campi del ruolo (mai il gold completo), così il
few-shot non espone story, question, query o risultati estranei al compito.

:author: Riccardo Morabito
"""

from typing import Callable, ClassVar


class RoleExampleBuilder:
    """Proietta un task accettato negli esempi role-specific per il few-shot.

    Stateless e puro: nessuna I/O; la proiezione ruolo->campi è definita in un
    unico punto (``_BUILDERS``) e usata dal promotore per scrivere i file.
    """

    @staticmethod
    def _spec_example(task: dict) -> dict:
        """Esempio spec: la specifica intera (è l'artefatto che il ruolo produce)."""
        return task["spec"]

    @staticmethod
    def _schema_example(task: dict) -> dict:
        """Esempio schema: coppia spec -> schema_ddl."""
        return {"spec": task["spec"], "schema_ddl": task["gold"]["schema_ddl"]}

    @staticmethod
    def _data_example(task: dict) -> dict:
        """Esempio data: spec + schema_ddl -> data_spec (la DataSpec sostituisce le INSERT)."""
        return {
            "spec": task["spec"],
            "schema_ddl": task["gold"]["schema_ddl"],
            "data_spec": task["gold"]["data_spec"],
        }

    @staticmethod
    def _query_example(task: dict) -> dict:
        """Esempio query: schema_ddl + data_profile + feature_sql -> query gold."""
        return {
            "schema_ddl": task["gold"]["schema_ddl"],
            "data_profile": task["gold"]["data_profile"],
            "feature_sql": task["spec"]["sql_features"],
            "query": task["gold"]["query"],
        }

    @staticmethod
    def _story_example(task: dict) -> dict:
        """Esempio story: schema_ddl + data_profile -> story."""
        return {
            "schema_ddl": task["gold"]["schema_ddl"],
            "data_profile": task["gold"]["data_profile"],
            "story": task["story"],
        }

    @staticmethod
    def _question_example(task: dict) -> dict:
        """Esempio question: story -> question."""
        return {"story": task["story"], "question": task["question"]}

    _BUILDERS: ClassVar[dict[str, Callable[[dict], dict]]] = {
        "spec": _spec_example,
        "schema": _schema_example,
        "data": _data_example,
        "query": _query_example,
        "story": _story_example,
        "question": _question_example,
    }

    def build(self, task: dict, role: str) -> dict:
        """Restituisce l'esempio role-specific del task accettato."""
        builder = self._BUILDERS.get(role)
        if builder is None:
            msg = f"Nessuna proiezione esempi per il ruolo: {role!r}"
            raise ValueError(msg)
        return builder(task)

    def roles(self) -> tuple[str, ...]:
        """Restituisce i ruoli generativi con proiezione esempi, in ordine stabile."""
        return tuple(self._BUILDERS)
