-- Estado de execucao (sessoes, mensagens, consumo). Separado da base operacional, que e
-- reconstruida a cada build a partir dos CSVs e nunca recebe escrita.

CREATE TABLE IF NOT EXISTS sessions (
    session_id    TEXT PRIMARY KEY,
    token_hash    TEXT NOT NULL UNIQUE,
    created_at    TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    revoked_at    TEXT,
    customer_id   INTEGER,
    customer_name TEXT,
    budget_tokens INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_hash ON sessions(token_hash);

CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    guard      TEXT,
    created_at TEXT NOT NULL,
    latency_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, message_id);

CREATE TABLE IF NOT EXISTS usage_ledger (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    tokens_in      INTEGER NOT NULL DEFAULT 0,
    tokens_out     INTEGER NOT NULL DEFAULT 0,
    tools          TEXT,
    guard          TEXT,
    latency_ms     INTEGER,
    prompt_version TEXT,
    model          TEXT,
    created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_session ON usage_ledger(session_id);
