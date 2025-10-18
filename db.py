from contextlib import contextmanager
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
load_dotenv()

from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

pool = None

def setup():
    global pool
    DATABASE_URL = os.environ['DATABASE_URL']
    pool = ThreadedConnectionPool(1, 100, dsn=DATABASE_URL, sslmode='require')

@contextmanager
def get_db_connection():
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)

@contextmanager
def get_db_cursor(commit=False):
    with get_db_connection() as connection:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            if commit:
                connection.commit()
        finally:
            cursor.close()

def upsert_user(auth0_id, name, email):
    """
    Insert or update user, return user_id.

    - Saves provided `name` into users.name (desired behavior).
    - Won’t overwrite existing non-empty name with empty/NULL.
    """
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO users (auth0_id, name, email, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            ON CONFLICT (auth0_id) DO UPDATE
            SET name       = COALESCE(NULLIF(EXCLUDED.name, ''), users.name),
                email      = EXCLUDED.email,
                updated_at = NOW()
            RETURNING id;
        """, (auth0_id, name, email))
        row = cur.fetchone()
        return row["id"]

def get_clash_details(clash_id):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT c.id, c.title, c.description, c.owner_id, u.name as owner_name
            FROM clash c
            JOIN users u ON u.id = c.owner_id
            WHERE c.id = %s
        """, (clash_id,))
        return cur.fetchone()

def get_arguments_by_clash_id(clash_id):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT a.id, a.owner_id, u.name, a.content, a.argument_type, a.parent_id
            FROM arguments a
            JOIN users u ON u.id = a.owner_id
            WHERE a.clash_id = %s AND a.parent_id IS NULL
            GROUP BY a.id, u.name
            ORDER BY a.created_at ASC
        """, (clash_id,))
        return cur.fetchall()

def create_argument(clash_id, user_id, content, argument_type, parent_id=None):
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO arguments (clash_id, owner_id, content, argument_type, parent_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (clash_id, user_id, content, argument_type, parent_id, datetime.now()))

def get_replies_by_clash_id(clash_id):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT a.id, a.owner_id, u.name, a.content, a.argument_type, a.parent_id, 0
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
    
def add_new_tag(new_tag):
    with get_db_cursor(commit=True) as cur:
        cur.execute("INSERT INTO tags (name) VALUES (%s) RETURNING id;", 
                    (new_tag,)
                    )
        row = cur.fetchone()
        if row is None:
            raise Exception("Failed to insert new tag")
        # returning the id of the new tag so that I can add it to 
        new_tag_id = row['id']
    return new_tag_id

def get_clashes_by_tag(tag_name, limit, offset):
    with get_db_cursor() as cur:
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

        cur.execute("""
            SELECT COUNT(*) FROM clash_dump c
            JOIN clash_tags_dump ct ON c.id = ct.clash_id
            JOIN tags t ON ct.tag_id = t.id
            WHERE t.name = %s;
        """, (tag_name,))
        total = cur.fetchone()['count']

    return clashes, total

def vote_argument(arg_id, vote):
    column = "up_votes" if vote > 0 else "down_votes"
    with get_db_cursor(commit=True) as cur:
        cur.execute(f"""
            UPDATE arguments 
            SET {column} = {column} + 1
            WHERE id = %s
            RETURNING clash_id;
        """, (arg_id,))
        result = cur.fetchone()
        return result["clash_id"] if result else None

def add_clash(owner_id, title, description, close_date):
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO clash (start_time, end_time, status, title, description, owner_id)
            VALUES (%s, %s, %s, %s, %s, %s) 
            RETURNING id;
        """, (datetime.now(), close_date, "open", title, description, owner_id))
        # have to do this to fetch the id of this new 
        row = cur.fetchone()
        if row is None:
            raise Exception("Failed to insert clash!")
        new_clash_id = row['id']
    return new_clash_id

def add_clash_tag(tag_id, clash_id):
    with get_db_cursor(commit=True) as cur:
        cur.execute("INSERT INTO clash_tag (tag_id, clash_id) VALUES (%s, %s);", (tag_id, clash_id))
        return None

def search_clashes(query, sort_by, status, start_date, end_date, limit, offset, category=None):
    with get_db_cursor() as cur:
        conditions = []
        params = []
        order_clause = "ORDER BY created_at DESC"

        if query:
            conditions.append("search_vector @@ plainto_tsquery('english', %s)")
            params.append(query)

        if status in ["open", "closed"]:
            conditions.append("status = %s")
            params.append(status)

        if start_date and end_date:
            conditions.append("(start_time >= %s AND end_time <= %s)")
            params.extend([start_date, end_date])

        if category:
            conditions.append("""
                id IN (
                    SELECT ct.clash_id
                    FROM clash_tags_dump ct
                    JOIN tags t ON t.id = ct.tag_id
                    WHERE t.name = %s
                )
            """)
            params.append(category)

        if sort_by == "most_voted":
            order_clause = "ORDER BY up_votes DESC"
        elif sort_by == "least_voted":
            order_clause = "ORDER BY up_votes ASC"

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        cur.execute(f"""
            SELECT id, title, description, status, created_at,
                   ts_rank_cd(search_vector, plainto_tsquery('english', %s)) AS rank
            FROM clash_dump
            {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s;
        """, [query or ""] + params + [limit, offset])
        clashes = [dict(row) for row in cur.fetchall()]

        cur.execute(f"""
            SELECT COUNT(*) AS count
            FROM clash_dump
            {where_clause};
        """, params)
        total = cur.fetchone()["count"]

        return clashes, total


def update_username(user_id, new_name):
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE users
            SET name = %s, updated_at = NOW()
            WHERE id = %s
        """, (new_name, user_id))


def delete_user(user_id):
    with get_db_cursor(commit=True) as cur:
        try:
            # Delete arguments & replies made by user
            cur.execute("DELETE FROM arguments WHERE owner_id = %s;", (user_id,))

            # Delete clashes created by user (and their tag mappings if any)
            cur.execute("""
                DELETE FROM clash_tags_dump
                WHERE clash_id IN (SELECT id FROM clash WHERE owner_id = %s);
            """, (user_id,))
            cur.execute("DELETE FROM clash WHERE owner_id = %s;", (user_id,))

            # Finally delete user record
            cur.execute("DELETE FROM users WHERE id = %s;", (user_id,))
            return True
        except Exception as e:
            print(f"⚠️ Delete failed for user {user_id}: {e}")
            return False
    
def close_expired_items():
    now_utc = datetime.now(timezone.utc)
    # today_chicago = (now_utc - timedelta(hours=5)).date()
    with get_db_cursor as cur:
        cur.execute(
            """
                UPDATE clash_dump
                SET status = 'closed'
                WHERE close_date = %s AND status != 'closed';
            """,(now_utc,)
        )
        closed_clashes = cur.rowcount

        cur.execute("""
            UPDATE community
            SET status = 'closed'
            WHERE end_time = %s AND status != 'closed';
        """, (now_utc,))
        closed_communities = cur.rowcount

    return closed_clashes, closed_communities

