import sqlite3
import os
import config
from database.models import ALL_TABLES


def get_connection():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        for statement in ALL_TABLES:
            conn.execute(statement)
        conn.commit()
