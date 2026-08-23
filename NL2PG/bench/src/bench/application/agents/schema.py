"""Agente per la generazione dello schema DDL.

:author: Riccardo Morabito
"""

from sqlglot import exp, parse

from typing import Any, ClassVar

from bench.application.agents.base import AbstractAgent
from bench.application.validators.schema_validator import SchemaValidator
from bench.domain.models.category import CategoryDTO
from bench.domain.models.sql import SchemaDDLDTO
from bench.domain.models.state import TaskStateDTO
from bench.domain.ports.outbound.config_port import ConfigPort
from bench.domain.ports.outbound.example_port import ExamplePort
from bench.domain.ports.outbound.llm_port import LLMGeneratorPort
from bench.domain.ports.outbound.prompt_port import PromptPort
from bench.domain.services.validation.sql_repair import PostgresSQLRepair


class SchemaAgent(AbstractAgent):
    """Genera SchemaDDLDTO via LLM e lo valida eseguendolo nel sandbox PostgreSQL."""

    def __init__(
        self,
        llm: LLMGeneratorPort,
        prompts: PromptPort,
        config: ConfigPort,
        validator: SchemaValidator,
        examples: ExamplePort | None = None,
    ) -> None:
        """Inietta le porte outbound, gli esempi e il validatore schema."""
        super().__init__(llm, prompts, config, examples)
        self._validator = validator
        self._repair = PostgresSQLRepair()

    def prompt_name(self) -> str:
        """Restituisce 'schema' come nome del template prompt."""
        return "schema"

    def build_kwargs(self, state: TaskStateDTO) -> dict:
        """Costruisce i kwargs per il prompt con tipo schema, descrizione, spec e few-shot."""
        few_shot = self._few_shot(state)
        cat = self._config.load_categories().get(state.category, CategoryDTO())
        return {
            "cat_tipo_schema": cat.tipo_schema,
            "cat_descrizione": cat.descrizione,
            "spec": state.spec.model_dump_json() if state.spec else "{}",
            "few_shot": few_shot,
        }

    def output_schema(self) -> type:
        """Restituisce SchemaDDLDTO come schema per lo structured output."""
        return SchemaDDLDTO

    def validate(self, output: SchemaDDLDTO, state: TaskStateDTO) -> tuple[bool, str, dict]:
        """Valida il DDL eseguendolo nel sandbox e verificando tipo e numero di tabelle."""
        cat = self._config.load_categories().get(state.category, CategoryDTO())
        result = self._validator.validate_with_type(output, state.sandbox_schema, cat.tipo_schema)
        if not result.is_valid:
            return (False, result.error, {})
        en_err = self._check_italian_identifiers(output.ddl)
        if en_err:
            return (False, en_err, {})
        actual = self._validator.table_count(state.sandbox_schema)
        if actual < 1:
            return (False, "Lo script DDL non crea alcuna tabella valida nel database", {})
        min_tab = cat.n_tables_range[0] if cat.n_tables_range else 1
        max_tab = cat.n_tables_range[1] if cat.n_tables_range else 12
        if not (min_tab <= actual <= max_tab):
            msg = f"DDL con {actual} tabelle, ma la categoria ammette tra {min_tab} e {max_tab}"
            return (False, msg, {})
        return (True, "", {})

    _EN_IDENTS: ClassVar[dict[str, str]] = {
        "first_name": "nome",
        "last_name": "cognome",
        "full_name": "nome_completo",
        "birth_date": "data_nascita",
        "hire_date": "data_assunzione",
        "start_date": "data_inizio",
        "end_date": "data_fine",
        "salary": "stipendio",
        "price": "prezzo",
        "amount": "importo",
        "quantity": "quantita",
        "qty": "quantita",
        "address": "indirizzo",
        "city": "citta",
        "country": "paese",
        "phone": "telefono",
        "customer": "cliente",
        "employee": "dipendente",
        "supplier": "fornitore",
        "warehouse": "magazzino",
    }

    def _check_italian_identifiers(self, ddl: str) -> str:
        """Respinge DDL con identificatori inglesi non ammessi dal contratto naming."""
        try:
            idents: set[str] = set()
            for st in parse(ddl, read="postgres"):
                if isinstance(st, exp.Create) and isinstance(st.this, exp.Schema):
                    tname = getattr(st.this.this, "name", None)
                    if tname and str(tname).lower() in self._EN_IDENTS:
                        idents.add(str(tname))
                    for e in st.this.expressions or []:
                        if isinstance(e, exp.ColumnDef) and str(e.name).lower() in self._EN_IDENTS:
                            idents.add(str(e.name))
        except Exception:  # noqa: BLE001
            return ""
        if not idents:
            return ""
        sug = ", ".join(f"{k} → {self._EN_IDENTS[k]}" for k in sorted(idents)[:6])
        return (
            "Il benchmark e' in italiano: gli identificatori devono essere italiani. "
            f"Trovati nomi inglesi non ammessi: {sug}. Rinominali con l'equivalente italiano."
        )

    def build_updates(self, output: SchemaDDLDTO, state: TaskStateDTO) -> dict:
        """Aggiorna lo stato con il DDL riparato e sincronizza n_tables nella Spec."""
        actual = self._validator.table_count(state.sandbox_schema)
        repaired_ddl = self._repair.repair(output.ddl)
        updates: dict[str, Any] = {"schema_ddl": SchemaDDLDTO(ddl=repaired_ddl)}
        if state.spec and actual > 0 and state.spec.n_tables != actual:
            updates["spec"] = state.spec.model_copy(update={"n_tables": actual})
        return updates
