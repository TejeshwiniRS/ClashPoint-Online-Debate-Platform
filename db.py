from contextlib import contextmanager
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from flask import current_app, g

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

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
      cursor = connection.cursor(cursor_factory=RealDictCursor)
      # cursor = connection.cursor()
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
    
def create_argument(clash_id, user_id, content, argument_type, parent_id=None):
    with get_db_cursor(commit=True) as cur:
        cur.execute(""" INSERT INTO arguments (clash_id, owner_id, content, argument_type, parent_id, created_at) VALUES (%s, %s, %s, %s, %s, %s)""", (clash_id, user_id, content, argument_type, parent_id, datetime.now()))

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

def get_all_tags():
    with get_db_cursor() as cur:
        cur.execute("SELECT id, name FROM tags ORDER BY name;")
        return [dict(row) for row in cur.fetchall()]


def get_clashes_by_tag(tag_name, limit, offset):
    with get_db_cursor() as cur:
        # Get clashes linked to this tag
        cur.execute("""
            SELECT c.id, c.title, c.description, c.created_at, c.status
            FROM clash_dump c
            JOIN clash_tags_dump ct ON c.id = ct.clash_id
            JOIN tags t ON ct.tag_id = t.id
            WHERE t.name = %s
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s;
        """, (tag_name, limit, offset))
        clashes = [dict(row) for row in cur.fetchall()]

        # Count total for pagination
        cur.execute("""
            SELECT COUNT(*) FROM clash_dump c
            JOIN clash_tags_dump ct ON c.id = ct.clash_id
            JOIN tags t ON ct.tag_id = t.id
            WHERE t.name = %s;
        """, (tag_name,))
        total = cur.fetchone()['count']

    return clashes, total

def vote_argument(arg_id, vote):
    print(arg_id, vote)
    column = "up_votes" if vote > 0 else "down_votes"
    print(column)
    with get_db_cursor(commit=True) as cur:
        cur.execute(f"""
            UPDATE arguments 
            SET {column} = {column} + 1
            WHERE id = {arg_id}
            RETURNING clash_id;
        """)
        result = cur.fetchone()
        if result:
            return result["clash_id"]
        else:
            return None