-- Database schema for the application
-- Generated from SQLModel classes

-- Create user table
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create session table
CREATE TABLE IF NOT EXISTS session (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);

-- Create thread table
CREATE TABLE IF NOT EXISTS thread (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for frequently queried columns
CREATE INDEX IF NOT EXISTS idx_user_email ON user(email);
CREATE INDEX IF NOT EXISTS idx_session_user_id ON session(user_id);
