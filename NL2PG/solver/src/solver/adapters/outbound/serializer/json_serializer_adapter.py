"""Adattatore per la serializzazione atomica JSON delle run del solver tramite orjson.

:author: Riccardo Morabito
"""

from pathlib import Path

from orjson import OPT_INDENT_2, dumps as orjson_dumps, loads as orjson_loads

from solver.domain.models.solver import SolverRunDTO
from solver.domain.ports.outbound.serializer_port import SerializerPort


class JsonSerializerAdapter(SerializerPort):
    """Adattatore outbound per la serializzazione atomica su filesystem via orjson."""

    def save_run(self, run_dto: SolverRunDTO, output_dir: Path) -> Path:
        """Salva atomicamente il SolverRunDTO in formato JSON su file temporaneo e lo rimpiazza."""
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"solver_{run_dto.run_id}.json"
        target_path = output_dir / filename
        tmp_path = target_path.with_suffix(".tmp")

        data = run_dto.model_dump(mode="json")
        payload = orjson_dumps(data, option=OPT_INDENT_2)
        tmp_path.write_bytes(payload)
        tmp_path.replace(target_path)

        return target_path

    def load_run(self, json_path: Path) -> SolverRunDTO:
        """Carica e deserializza un SolverRunDTO da un file JSON."""
        data = orjson_loads(json_path.read_bytes())
        return SolverRunDTO.model_validate(data)
