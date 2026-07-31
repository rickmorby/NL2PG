"""Mapper per la conversione tra DTO ed Entità ORM.

:author: Riccardo Morabito
"""

from json import dumps
from bench.adapters.outbound.postgres.entities import TaskEntity
from bench.domain.models.state import TaskStateDTO


class TaskStateMapper:
    """Mapper per la conversione di TaskStateDTO in TaskEntity."""

    @staticmethod
    def dto_to_entity(run_id: str, state: TaskStateDTO) -> TaskEntity:
        """Converte un TaskStateDTO in una TaskEntity per il salvataggio."""
        spec = state.spec
        schema = state.schema_ddl
        data = state.data_inserts
        gold_q = state.gold_query
        gold_r = state.gold_result
        story = state.story
        question = state.question
        critic = state.critic
        calib = state.calibration

        return TaskEntity(
            task_id=state.task_id,
            run_id=run_id,
            category=state.category,
            spec_hash=spec.spec_hash if spec else None,
            verdict=state.verdict,
            difficulty_label=state.difficulty_label,
            critic_score=critic.narrative if critic else None,
            pass_rate=calib.pass_rate if calib else None,
            judge_verdict=state.judge_verdict,
            last_model=state.last_model,
            retry_schema=state.retry_schema,
            retry_data=state.retry_data,
            retry_query=state.retry_query,
            retry_story=state.retry_story,
            retry_question=state.retry_question,
            retry_critic=state.retry_critic,
            retry_hardening=state.retry_hardening,
            judge_regens=state.judge_regens,
            last_error=state.last_error,
            schema_ddl=schema.ddl if schema else None,
            data_inserts=data.inserts if data else None,
            gold_query=gold_q.query if gold_q else None,
            gold_result=dumps(gold_r.model_dump(), ensure_ascii=False) if gold_r else None,
            story=story.story if story else None,
            question=question.question if question else None,
            spec=dumps(spec.model_dump(), ensure_ascii=False) if spec else None,
        )

