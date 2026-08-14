"""
database.py — SQLite Local Connection & Schema Setup
"""

import sqlite3
import pandas as pd
import streamlit as st

DB_FILE = "pharmacy.db"


def get_connection():
    """Returns a SQLite connection with dict-like row access enabled."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def query(sql: str, params: tuple = ()):
    """Run a SELECT query and return a list of plain dicts."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def query_one(sql: str, params: tuple = ()):
    """Run a SELECT query and return a single row dict, or None."""
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = ()):
    """Run an INSERT/UPDATE/DELETE statement inside a transaction."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.lastrowid


def get_dataframe(sql: str, params: tuple = ()):
    """Utility to load query results straight into a Pandas DataFrame."""
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)
