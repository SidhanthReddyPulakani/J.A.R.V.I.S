"""
Jarvis SQLite database schema.

This module contains the SQL required to create the initial
Jarvis database structure.
"""

SCHEMA_VERSION = 1


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
-- Memories
-- --------------------------------------------------

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    content TEXT NOT NULL,

    category TEXT,
    subject TEXT,
    project TEXT,

    importance REAL DEFAULT 0.5,
    confidence REAL DEFAULT 1.0,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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