CREATE DATABASE bench_meta OWNER bench;

\c bench_meta

CREATE SCHEMA IF NOT EXISTS bench_meta;

CREATE TABLE IF NOT EXISTS bench_meta.runs (
    id              TEXT PRIMARY KEY,
    config_hash     TEXT NOT NULL,
    categories_hash TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bench_meta.tasks (
    task_id           TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES bench_meta.runs(id),
    category          TEXT NOT NULL,
    spec_hash         TEXT,
    verdict           TEXT NOT NULL,
    difficulty_label  TEXT,
    critic_score      REAL,
    pass_rate         REAL,
    judge_verdict     TEXT,
    last_model        TEXT,
    retry_schema      INT DEFAULT 0,
    retry_data        INT DEFAULT 0,
    retry_query       INT DEFAULT 0,
    retry_story       INT DEFAULT 0,
    retry_question    INT DEFAULT 0,
    retry_critic      INT DEFAULT 0,
    retry_hardening   INT DEFAULT 0,
    judge_regens      INT DEFAULT 0,
    last_error        TEXT,
    schema_ddl        TEXT,
    data_inserts      TEXT,
    gold_query        TEXT,
    gold_result       TEXT,
    story             TEXT,
    question          TEXT,
    spec              TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bench_meta.failovers (
    id         BIGSERIAL PRIMARY KEY,
    task_id    TEXT,
    role       TEXT NOT NULL,
    from_model TEXT NOT NULL,
    to_model   TEXT NOT NULL,
    reason     TEXT NOT NULL,
    ts         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tasks_category  ON bench_meta.tasks(category);
CREATE INDEX IF NOT EXISTS idx_tasks_run_id    ON bench_meta.tasks(run_id);
CREATE INDEX IF NOT EXISTS idx_tasks_spec_hash ON bench_meta.tasks(spec_hash);
CREATE INDEX IF NOT EXISTS idx_failovers_task  ON bench_meta.failovers(task_id);
