from contextlib import contextmanager
import logging
import os
from dotenv import load_dotenv
load_dotenv()
from flask import current_app, g

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import DictCursor

pool = None

def setup():
    global pool
    DATABASE_URL = os.environ['DATABASE_URL']
    pool = ThreadedConnectionPool(1, 100, dsn=DATABASE_URL, sslmode='require')


@contextmanager
def get_db_connection():
    try:
        connection = pool.getconn()
        yield connection
    finally:
        pool.putconn(connection)


@contextmanager
def get_db_cursor(commit=False):
    with get_db_connection() as connection:
      cursor = connection.cursor(cursor_factory=DictCursor)
      try:
          yield cursor
          if commit:
              connection.commit()
      finally:
          cursor.close()

def upsert_user(auth0_id, name, email):
    """Insert or update user, return user_id"""
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO users (auth0_id, name, email, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            ON CONFLICT (auth0_id) DO UPDATE
            SET name = EXCLUDED.name,
                email = EXCLUDED.email,
                updated_at = NOW()
            RETURNING id;
        """, (auth0_id, name, email))
        row = cur.fetchone()
        return row["id"]

