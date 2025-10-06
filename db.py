from contextlib import contextmanager
import logging
import os
from datetime import datetime

from flask import current_app, g

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

pool = None

def setup():
    global pool
    DATABASE_URL = os.environ['DATABASE_URL']
    # current_app.logger.info(f"creating db connection pool")
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
      cursor = connection.cursor(cursor_factory=RealDictCursor)
      # cursor = connection.cursor()
      try:
          yield cursor
          if commit:
              connection.commit()
      finally:
          cursor.close()


def get_clash_details(clash_id):
    with get_db_cursor() as cur:
        cur.execute(""" SELECT c.id, c.title, c.description, c.owner_id, u.name as owner_name from clash c join users u on u.id = c.owner_id WHERE c.id = %s """, (clash_id,))
        return cur.fetchone()
    
def get_arguments_by_clash_id(clash_id):
    with get_db_cursor() as cur:
        cur.execute(""" SELECT a.id, a.owner_id, u.name, a.content, a.argument_type, a.parent_id FROM arguments a
            JOIN users u ON u.id = a.owner_id
            WHERE a.clash_id = %s AND a.parent_id IS NULL
            GROUP BY a.id, u.name
            ORDER BY a.created_at ASC """, (clash_id,))
        return cur.fetchall()
    
def create_argument(clash_id, user_id, content, stance, parent_id=None):
    with get_db_cursor(commit=True) as cur:
        cur.execute(""" INSERT INTO arguments (clash_id, owner_id, content, argument_type, parent_id, created_at) VALUES (%s, %s, %s, %s, %s, %s)""", (clash_id, user_id, content, stance, parent_id, datetime.now()))

def get_replies_by_clash_id(clash_id):
    with get_db_cursor() as cur:
        cur.execute(""" SELECT a.id, a.owner_id, u.name, a.content, a.argument_type, a.parent_id, 0
                        FROM arguments a
                        JOIN users u ON u.id = a.owner_id
                        WHERE a.clash_id = %s AND a.parent_id IS NOT NULL
                        GROUP BY a.id, u.name
                        ORDER BY a.created_at ASC
                    """, (clash_id,))
        return cur.fetchall()


# Will remove later
# def vote_argument(arg_id, user_id, vote_value):
#     with get_db_cursor(commit=True) as cur:
#         cur.execute("""
#             INSERT INTO votes (argument_id, user_id, vote_value)
#             VALUES (%s, %s, %s)
#             ON CONFLICT (argument_id, user_id)
#             DO UPDATE SET vote_value = EXCLUDED.vote_value
#         """, (arg_id, user_id, vote_value))

#         # return clash id for redirect
#         cur.execute("SELECT clash_id FROM arguments WHERE id = %s", (arg_id,))
#         clash = cur.fetchone()
#         return clash["clash_id"] if clash else None