import Database from 'better-sqlite3';
import fs from 'node:fs';
import { runtimePaths } from '../config/runtime-paths.js';

const dbDir = runtimePaths.dbDir;
const dbPath = runtimePaths.dbPath;

if (!fs.existsSync(dbDir)) {
  fs.mkdirSync(dbDir, { recursive: true });
}

const database = new Database(dbPath);

database.pragma('journal_mode = WAL');

database.exec(`
  CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT,
    status TEXT NOT NULL DEFAULT 'off'
      CHECK (status IN ('off', 'idle', 'error', 'maintenance')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT
  )
`);

export default database;
