"""Database setup and simple access functions."""
import os
import sqlite3
import json
from contextlib import contextmanager

from app.contract.schemas import Telemetry, TwinState, Event

DB_URL = os.environ.get("DB_URL", "sqlite:///./fleettwin.db")
# Strip sqlite:/// prefix
db_path = DB_URL.replace("sqlite:///", "")

# Use a module-level connection with check_same_thread=False for easy access in the app
conn = sqlite3.connect(db_path, check_same_thread=False)
conn.row_factory = sqlite3.Row

def init_db():
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS robots (
        robot_id TEXT PRIMARY KEY,
        robot_type TEXT
    );
    CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        robot_id TEXT,
        ts REAL,
        data TEXT
    );
    CREATE TABLE IF NOT EXISTS twin_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        robot_id TEXT,
        ts REAL,
        data TEXT
    );
    CREATE TABLE IF NOT EXISTS events (
        event_id TEXT PRIMARY KEY,
        robot_id TEXT,
        ts REAL,
        kind TEXT,
        severity TEXT,
        data TEXT
    );
    CREATE TABLE IF NOT EXISTS missions (
        mission_id TEXT PRIMARY KEY,
        robot_id TEXT,
        data TEXT
    );
    CREATE TABLE IF NOT EXISTS eval_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        data TEXT
    );
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        role TEXT,
        password_hash TEXT
    );
    
    CREATE INDEX IF NOT EXISTS idx_telemetry_robot_ts ON telemetry(robot_id, ts);
    CREATE INDEX IF NOT EXISTS idx_twin_robot_ts ON twin_state(robot_id, ts);
    CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
    """)
    conn.commit()

def insert_telemetry(tel: Telemetry):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO telemetry (robot_id, ts, data) VALUES (?, ?, ?)",
        (tel.robot_id, tel.ts, tel.model_dump_json())
    )
    conn.commit()

def insert_twin_state(state: TwinState):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO twin_state (robot_id, ts, data) VALUES (?, ?, ?)",
        (state.robot_id, state.ts, state.model_dump_json())
    )
    conn.commit()

def insert_event(evt: Event):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO events (event_id, robot_id, ts, kind, severity, data) VALUES (?, ?, ?, ?, ?, ?)",
        (evt.id, evt.robot_id, evt.ts, evt.kind, evt.severity, evt.model_dump_json())
    )
    conn.commit()

# Fast memory caches for the API (last 120 states, last 50 events per robot)
# This avoids doing expensive DB reads on the main thread for SSE streams
import collections

history_cache: dict[str, collections.deque] = collections.defaultdict(
    lambda: collections.deque(maxlen=120)
)
events_cache: collections.deque = collections.deque(maxlen=50)

def append_history(state: TwinState):
    history_cache[state.robot_id].append(state)

def append_event_cache(evt: Event):
    events_cache.append(evt)
