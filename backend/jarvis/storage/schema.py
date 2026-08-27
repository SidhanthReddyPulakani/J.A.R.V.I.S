"""
Jarvis SQLite database schema.

This module contains the SQL required to create the initial
Jarvis database structure.
"""

SCHEMA_VERSION = 5


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

-- --------------------------------------------------
-- Conversations
-- --------------------------------------------------

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);


-- --------------------------------------------------
-- Messages
-- --------------------------------------------------

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    conversation_id INTEGER NOT NULL,

    role TEXT NOT NULL,
    content TEXT NOT NULL,

    created_at TEXT NOT NULL,

    FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS idx_messages_conversation
ON messages(conversation_id);


CREATE INDEX IF NOT EXISTS idx_messages_created_at
ON messages(created_at);


-- --------------------------------------------------
-- Agent State
-- --------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_state (
    agent_id TEXT PRIMARY KEY,

    conversation_id INTEGER,

    current_task TEXT,
    current_goal TEXT,

    mode TEXT NOT NULL DEFAULT 'idle',

    active_project TEXT,

    active_operation TEXT,
    operation_status TEXT NOT NULL DEFAULT 'idle',

    updated_at TEXT NOT NULL,

    FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE SET NULL
);


-- --------------------------------------------------
-- Core Memory
-- --------------------------------------------------

CREATE TABLE IF NOT EXISTS core_memory_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    agent_id TEXT NOT NULL,

    label TEXT NOT NULL,

    content TEXT NOT NULL DEFAULT '',

    capacity INTEGER NOT NULL DEFAULT 2000,

    priority INTEGER NOT NULL DEFAULT 100,

    writable INTEGER NOT NULL DEFAULT 1,

    created_at TEXT NOT NULL,

    updated_at TEXT NOT NULL,

    UNIQUE(agent_id, label),

    FOREIGN KEY (agent_id)
        REFERENCES agent_state(agent_id)
        ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS idx_core_memory_agent
ON core_memory_blocks(agent_id);


CREATE INDEX IF NOT EXISTS idx_core_memory_priority
ON core_memory_blocks(
    agent_id,
    priority
);

-- --------------------------------------------------
-- Diary Events
-- --------------------------------------------------

CREATE TABLE IF NOT EXISTS diary_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    agent_id TEXT NOT NULL,

    conversation_id INTEGER,

    event_type TEXT NOT NULL,

    description TEXT NOT NULL,

    source TEXT,

    metadata TEXT NOT NULL DEFAULT '{}',

    created_at TEXT NOT NULL,

    FOREIGN KEY (agent_id)
        REFERENCES agent_state(agent_id)
        ON DELETE CASCADE,

    FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE SET NULL
);


CREATE INDEX IF NOT EXISTS idx_diary_agent
ON diary_events(agent_id);


CREATE INDEX IF NOT EXISTS idx_diary_conversation
ON diary_events(conversation_id);


CREATE INDEX IF NOT EXISTS idx_diary_type
ON diary_events(
    agent_id,
    event_type
);


CREATE INDEX IF NOT EXISTS idx_diary_created_at
ON diary_events(
    agent_id,
    created_at
);

-- --------------------------------------------------
-- Long-Term Memory
-- --------------------------------------------------

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    agent_id TEXT NOT NULL DEFAULT 'jarvis',

    content TEXT NOT NULL,

    category TEXT,
    subject TEXT,
    project TEXT,

    importance REAL NOT NULL DEFAULT 0.5,
    confidence REAL NOT NULL DEFAULT 1.0,

    status TEXT NOT NULL DEFAULT 'active',

    superseded_by_id INTEGER,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CHECK (
        importance >= 0.0
        AND importance <= 1.0
    ),

    CHECK (
        confidence >= 0.0
        AND confidence <= 1.0
    ),

    CHECK (
        status IN (
            'active',
            'superseded'
        )
    ),

    CHECK (
        superseded_by_id IS NULL
        OR superseded_by_id != id
    ),

    FOREIGN KEY (superseded_by_id)
        REFERENCES memories(id)
        ON DELETE RESTRICT
);


CREATE INDEX IF NOT EXISTS idx_memories_agent
ON memories(agent_id);


CREATE INDEX IF NOT EXISTS idx_memories_agent_status
ON memories(
    agent_id,
    status
);


CREATE INDEX IF NOT EXISTS idx_memories_subject
ON memories(subject);


CREATE INDEX IF NOT EXISTS idx_memories_project
ON memories(project);


-- --------------------------------------------------
-- Schedule events
-- --------------------------------------------------

CREATE TABLE IF NOT EXISTS schedule_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,
    description TEXT,

    start_time TEXT NOT NULL,
    end_time TEXT,

    location TEXT,

    recurrence TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);


CREATE INDEX IF NOT EXISTS idx_schedule_start_time
ON schedule_events(start_time);


-- --------------------------------------------------
-- Reminders
-- --------------------------------------------------

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,
    description TEXT,

    remind_at TEXT NOT NULL,

    recurrence TEXT,

    completed INTEGER NOT NULL DEFAULT 0,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);


CREATE INDEX IF NOT EXISTS idx_reminders_remind_at
ON reminders(remind_at);


CREATE INDEX IF NOT EXISTS idx_reminders_completed
ON reminders(completed);


-- --------------------------------------------------
-- Templates
-- --------------------------------------------------

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL UNIQUE,

    description TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);


-- --------------------------------------------------
-- Applications belonging to templates
-- --------------------------------------------------

CREATE TABLE IF NOT EXISTS template_apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    template_id INTEGER NOT NULL,

    name TEXT NOT NULL,

    target_type TEXT NOT NULL,
    target TEXT NOT NULL,

    created_at TEXT NOT NULL,

    FOREIGN KEY (template_id)
        REFERENCES templates(id)
        ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS idx_template_apps_template
ON template_apps(template_id);
"""