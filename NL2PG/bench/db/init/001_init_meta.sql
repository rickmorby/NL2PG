CREATE DATABASE bench_meta OWNER bench;

\c bench_meta

CREATE TABLE IF NOT EXISTS run_metadata (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    category VARCHAR(128),
    config_hash VARCHAR(64),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(32) DEFAULT 'pending',
    total_tasks INT DEFAULT 0,
    passed_tasks INT DEFAULT 0,
    failed_tasks INT DEFAULT 0
);