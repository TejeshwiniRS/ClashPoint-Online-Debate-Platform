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
        cur.execute(""" SELECT c.id, c.title, c.description, c.owner_id, u.name as owner_name, c.start_time, c.end_time from clash c join users u on u.id = c.owner_id WHERE c.id = %s AND c.status!='deleted'""", (clash_id,))
        clash = cur.fetchone()

        if not clash:
            return None
        
        cur.execute("""
            SELECT t.id, t.name
            FROM tags t
            JOIN clash_tag ct ON t.id = ct.tag_id
            WHERE ct.clash_id = %s;
        """, (clash_id,))
        tags = cur.fetchall() or []

        clash["tags"] = tags

        now = datetime.now()
        start_time = clash["start_time"]
        end_time = clash["end_time"]

        if start_time and now < start_time:
            clash["status"] = "not_started"
            clash["active_until_label"] = f"Clash will begin on {start_time.strftime('%b %d, %Y %I:%M %p')}"
        elif end_time and now > end_time:
            clash["status"] = "ended"
            clash["active_until_label"] = "Clash ended"
        else:
            clash["status"] = "active"
            clash["active_until_label"] = end_time.strftime('%b %d, %Y %I:%M %p') if end_time else "Ongoing"            

        return clash

    
def get_arguments_by_clash_id(clash_id):
    with get_db_cursor() as cur:
        cur.execute("""
                    SELECT a.id AS arg_id, a.clash_id AS clash_id, a.owner_id AS owner_id, a.argument_type AS argument_type, a.content AS content, a.parent_id AS parent_id, a.up_votes AS up_votes, a.down_votes as down_votes, a.created_at AS created_at, a.is_deleted as is_deleted, u.name as name 
                    FROM arguments a JOIN users u
                    ON u.id = a.owner_id
                    WHERE a.clash_id = %s AND a.parent_id IS NULL ORDER BY a.id ASC
                    """, (clash_id,))
        rows = cur.fetchall()
        for r in rows:
            r["id"] = r.pop("arg_id")
            up, down = r["up_votes"], r["down_votes"]
            r["score"] = 0.5 * up + 0.5 * down 
        return rows


def mark_argument_deleted(arg_id, user_id):
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE arguments
            SET is_deleted = TRUE, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND owner_id = %s
            RETURNING clash_id;
        """, (arg_id, user_id))
        row = cur.fetchone()
        return row["clash_id"] if row else None
def create_argument(clash_id, user_id, content, argument_type, parent_id=None):
    with get_db_cursor(commit=True) as cur:
        if parent_id:
            cur.execute("SELECT argument_type FROM arguments where id = %s", (parent_id,))
            parent = cur.fetchone()
            if parent:
                argument_type = parent["argument_type"]
        # print(clash_id, user_id, content, argument_type, parent_id)
        cur.execute(""" INSERT INTO arguments (clash_id, owner_id, content, argument_type, parent_id, created_at) VALUES (%s, %s, %s, %s, %s, %s)""", (clash_id, user_id, content, argument_type, parent_id, datetime.now()))

def get_replies_by_clash_id(clash_id):
    with get_db_cursor() as cur:
        cur.execute("""
                    SELECT a.id AS id, a.owner_id AS owner_id, a.argument_type AS argument_type, a.content AS content, a.parent_id AS parent_id, a.up_votes AS up_votes, a.down_votes as down_votes, a.created_at AS created_at, a.is_deleted as is_deleted, u.name as name 
                    FROM arguments a JOIN users u
                    ON u.id = a.owner_id
                    WHERE a.clash_id = %s AND a.parent_id IS NOT NULL ORDER BY a.created_at ASC
                    """, (clash_id,))
        rows = cur.fetchall()

    for row in rows:
        up, down = row["up_votes"], row["down_votes"]
        row["score"] = 0.5 * up + 0.5 * down

    return rows

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
            FROM clash c
            JOIN clash_tag ct ON c.id = ct.clash_id
            JOIN tags t ON ct.tag_id = t.id
            WHERE t.name = %s
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s;
        """, (tag_name, limit, offset))
        clashes = [dict(row) for row in cur.fetchall()]

        cur.execute("""
            SELECT COUNT(*) FROM clash c
            JOIN clash_tag ct ON c.id = ct.clash_id
            JOIN tags t ON ct.tag_id = t.id
            WHERE t.name = %s;
        """, (tag_name,))
        total = cur.fetchone()['count']

    return clashes, total

# Handle voting changes and feeding the vote count as changed to arguments table
def vote_argument(arg_id, vote):
    # print(arg_id, vote)
    column = "up_votes" if vote > 0 else "down_votes"
    # print(column)
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
        
def get_score(arg_id):
     with get_db_cursor() as cur:
        cur.execute("""
            SELECT up_votes, down_votes, (up_votes - down_votes) AS score
            FROM arguments
            WHERE id = %s;
        """, (arg_id,))
        return cur.fetchone()
        # row = cur.fetchone()
        # vote_score = max(row["up_votes"] - row["down_votes"], 0)
        # content = row["content"]
        # words = len(content.split()) if content else 0
        # max_words = 250
        # length_score = min(words, max_words) / max_words * 10 
        # weighted_score = 0.5 * vote_score + 0.5 * length_score
        # row["score"] = weighted_score
        # return row
        
def get_argument_by_id(arg_id):
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM arguments WHERE id = %s;", (arg_id,))
        return cur.fetchone()
def edit_argument(arg_id, content):
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE arguments 
            SET content = %s, updated_at = %s
            WHERE id = %s
            RETURNING clash_id;
        """, (content, datetime.now() , arg_id))
        result = cur.fetchone()
        if result:
            return result["clash_id"]
        else:
            return None

def delete_argument(arg_id):
    content = "----- deleted -----"
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE arguments 
            SET is_deleted = TRUE, updated_at = %s
            WHERE id = %s
            RETURNING clash_id;
        """, (datetime.now() , arg_id))
        result = cur.fetchone()
        if result:
            return result["clash_id"]
        else:
            return None
        
def get_trending_clashes(limit=5):
    with get_db_cursor() as cur:
        cur.execute(""" SELECT id, title, description FROM clash ORDER BY created_at  limit %s; """, (limit,))
        return cur.fetchall()
    
def get_related_clashes(clash_id, limit=5):
    with get_db_cursor() as cur:
        cur.execute(""" SELECT DISTINCT c.id, c.title, c.description, c.created_at
                        FROM clash c
                        JOIN clash_tag ct ON c.id = ct.clash_id
                        WHERE ct.tag_id IN (
                            SELECT tag_id FROM clash_tag WHERE clash_id = %s
                        )
                        AND c.id != %s
                        ORDER BY c.created_at DESC
                        LIMIT %s; """, (clash_id, clash_id, limit,))
        return cur.fetchall()
    
def arg_check_delete_status(arg_id):
    with get_db_cursor() as cur:
        cur.execute(""" SELECT is_deleted from arguments where id=%s """, (arg_id,))
        return cur.fetchone()     


def add_clash(owner_id, title, description, clash_close_date):
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO clash (start_time, end_time, status, title, description, owner_id)
            VALUES (%s, %s, %s, %s, %s, %s) 
            RETURNING id;
        """, (datetime.now(), clash_close_date, "open", title, description, owner_id))
        # have to do this to fetch the id of this new clash
        row = cur.fetchone()
        if row is None:
            raise Exception("Failed to insert clash!")
        new_clash_id = row['id']
    return new_clash_id

def update_clash(clash_id, title, description, close_date, owner_id, tag_id):
    with get_db_cursor(commit=True) as cur:
        fields = []
        params = []

        if title:
            fields.append("title = %s")
            params.append(title)

        if description:
            fields.append("description = %s")
            params.append(description)

        if close_date:
            fields.append("end_time = %s")
            params.append(close_date)

        fields.append("updated_at = NOW()")
        params.append(clash_id)
        params.append(owner_id)

        sql = f"""
            UPDATE clash
            SET {', '.join(fields)}
            WHERE id = %s AND owner_id = %s;
        """

        cur.execute(sql, params)

def delete_clash(clash_id):
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE clash SET status = %s WHERE id = %s;
        """ ,
        ( "deleted", clash_id)
        )
        
def add_community_clash(owner_id, title, description, clash_close_date, community_id):
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO clash (start_time, end_time, status, title, description, owner_id, community_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s) 
            RETURNING id;
        """, (datetime.now(), clash_close_date, "open", title, description, owner_id, community_id))
        # have to do this to fetch the id of this new clash
        row = cur.fetchone()
        if row is None:
            raise Exception("Failed to insert clash!")
        new_clash_id = row['id']
    return new_clash_id

def add_clash_tag(tag_id, clash_id):
    with get_db_cursor(commit=True) as cur:
        cur.execute("INSERT INTO clash_tag (tag_id, clash_id) VALUES (%s, %s);", (tag_id, clash_id))
        return None

# community CRUD operations 
def add_community(community_close_date, title, description, code, owner_id):
    with get_db_cursor(commit=True) as cur:
        cur.execute("""INSERT INTO community 
                    (start_time, 
                    end_time, 
                    status, 
                    title, 
                    description, 
                    secret_code_hash, 
                    owner_id, 
                    search_vector
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s, to_tsvector('english', %s || ' ' || %s) )
                    RETURNING ID
                    ;""",
                      (datetime.now(), community_close_date, "open", title, description, code, owner_id, title, description)
                    )
        row = cur.fetchone()
        if row is None:
            raise Exception("Failed to insert clash!")
        new_community_id = row['id']
    return new_community_id
    
def update_community(community_id, title, description, close_date, owner_id):
    with get_db_cursor(commit=True) as cur:
        fields = []
        params = []

        if title:
            fields.append("title = %s")
            params.append(title)

        if description:
            fields.append("description = %s")
            params.append(description)

        if close_date:
            fields.append("end_time = %s")
            params.append(close_date)

        fields.append("updated_at = NOW()")
        params.append(community_id)
        params.append(owner_id)

        sql = f"""
            UPDATE community
            SET {', '.join(fields)}
            WHERE id = %s AND owner_id = %s;
        """

        cur.execute(sql, params)

def delete_community(community_id):
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE community SET status = %s WHERE id = %s;
        """ ,
        ( "deleted", community_id)
        )

def search_clashes(query, sort_by, status, start_date, end_date, limit, offset, category=None, owner_id=None):
    with get_db_cursor() as cur:
        conditions = ["c.community_id IS NULL", "c.status != 'deleted'"]
        params = []
        joins = ""
        order_clause = "ORDER BY c.created_at DESC"

        if query:
            conditions.append("c.search_vector @@ plainto_tsquery('english', %s)")
            params.append(query)

        if status in ["open", "closed"]:
            conditions.append("c.status = %s")
            params.append(status)

        if start_date and end_date:
            conditions.append("(c.start_time >= %s AND c.end_time <= %s)")
            params.extend([start_date, end_date])

        if category:
            conditions.append("""
                c.id IN (
                    SELECT ct.clash_id
                    FROM clash_tag ct
                    JOIN tags t ON t.id = ct.tag_id
                    WHERE t.name = %s
                )
            """)
            params.append(category)

        if owner_id:
            conditions.append("c.owner_id = %s")
            params.append(owner_id)

        # Sorting logic
        if sort_by == "most_voted":
            # Only clashes that have at least one argument
            joins = """
                INNER JOIN (
                    SELECT clash_id, SUM(up_votes) AS total_up_votes
                    FROM arguments
                    GROUP BY clash_id
                ) AS a ON a.clash_id = c.id
            """
            order_clause = "ORDER BY a.total_up_votes DESC, c.created_at DESC"

        elif sort_by == "least_voted":
            # Include all clashes, but no-argument ones go last
            joins = """
                LEFT JOIN (
                    SELECT clash_id, SUM(up_votes) AS total_up_votes
                    FROM arguments
                    GROUP BY clash_id
                ) AS a ON a.clash_id = c.id
            """
            order_clause = "ORDER BY COALESCE(a.total_up_votes, 9999999) ASC, c.created_at DESC"

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        vote_select = "COALESCE(a.total_up_votes, 0)" if "JOIN" in joins else "0"

        # Main paginated query
        query_sql = f"""
            SELECT c.id, c.title, c.description, c.status, c.created_at,
                   {vote_select} AS total_up_votes,
                   ts_rank_cd(c.search_vector, plainto_tsquery('english', %s)) AS rank
            FROM clash c
            {joins}
            {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s;
        """
        cur.execute(query_sql, [query or ""] + params + [limit, offset])
        clashes = [dict(row) for row in cur.fetchall()]

        count_sql = f"""
            SELECT COUNT(*) AS count
            FROM clash c
            {joins}
            {where_clause};
        """
        cur.execute(count_sql, params)
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
                DELETE FROM clash_tag
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
                UPDATE clash
                SET status = 'closed'
                WHERE end_time = %s AND status != 'closed';
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

def search_communities(query, status, start_date, end_date, user_id=None, limit=6, offset=0):
    with get_db_cursor() as cur:
        conditions = ["status != 'deleted'"]
        params = []

        # --- Filters ---
        if query:
            conditions.append("search_vector @@ plainto_tsquery('english', %s)")
            params.append(query)

        if start_date and end_date:
            conditions.append("(start_time >= %s AND end_time <= %s)")
            params.extend([start_date, end_date])

        if user_id:
            conditions.append("""
                id IN (
                    SELECT community_id
                    FROM community_users
                    WHERE user_id = %s AND is_active_member = true
                )
            """)
            params.append(user_id)

        if status in ["open", "closed"]:
            conditions.append("status = %s")
            params.append(status)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        # --- Get total count ---
        count_sql = f"SELECT COUNT(*) AS total FROM community {where_clause};"
        cur.execute(count_sql, params)
        count_row = cur.fetchone()
        total = count_row["total"] if count_row and "total" in count_row else 0

        # --- Paginated query ---
        sql = f"""
            SELECT *
            FROM community
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s;
        """
        cur.execute(sql, params + [limit, offset])
        rows = [dict(row) for row in cur.fetchall()]

        return rows, total


    
def get_user_community_ids(user_id):
    with get_db_cursor() as cur:
        cur.execute("SELECT community_id FROM community_users WHERE user_id = %s", (user_id,))
        return [r['community_id'] for r in cur.fetchall()]
    
def add_user_to_community(user_id, community_id, role="member", is_active_member=True):
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO community_users (community_id, user_id, role, is_active_member, joined_at)
            VALUES (%s, %s, %s, %s, NOW());
        """, (community_id, user_id, role, is_active_member))

def verify_community_code(community_id, entered_code):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT secret_code_hash
            FROM community
            WHERE id = %s
            LIMIT 1;
        """, (community_id,))
        row = cur.fetchone()
        if not row:
            return False

        stored_code = (row.get("secret_code_hash") or "").strip()
        return stored_code == entered_code.strip()
    

def get_community_details(community_id):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT id, title, description, owner_id, start_time, end_time, status
            FROM community
            WHERE id = %s AND status!='deleted';
        """, (community_id,))
        return cur.fetchone()

def get_community_members(community_id):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT u.id, u.name, u.email
            FROM community_users cu
            JOIN users u ON cu.user_id = u.id
            WHERE cu.community_id = %s AND cu.is_active_member = true
            ORDER BY u.name ASC;
        """, (community_id,))
        return cur.fetchall()
    
def get_clashes_by_community(community_id, limit=6, offset=0):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) AS total
            FROM clash
            WHERE community_id = %s AND status != 'deleted';
        """, (community_id,))
        total = cur.fetchone()["total"]

        cur.execute("""
            SELECT id, title, description, status, created_at
            FROM clash
            WHERE community_id = %s AND status != 'deleted'
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s;
        """, (community_id, limit, offset))
        rows = [dict(row) for row in cur.fetchall()]

        return rows, total

    

def remove_community_member(community_id, email):
    with get_db_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE community_users
            SET is_active_member = false
            WHERE community_id = %s
                AND  user_id = (SELECT id from users WHERE email=%s)
                AND is_active_member = true;
        """, (community_id, email))
        return cur.rowcount > 0
    
def search_clashes_in_community(community_id, query):
    with get_db_cursor() as cur:
        like_pattern = f"%{query}%"
        cur.execute("""
            SELECT id, title, description, status, created_at
            FROM clash
            WHERE community_id = %s
              AND (title ILIKE %s OR description ILIKE %s)
            ORDER BY created_at DESC;
        """, (community_id, like_pattern, like_pattern))
        return [dict(row) for row in cur.fetchall()]


def get_trending_clashes(limit=5):
    with get_db_cursor() as cur:
        cur.execute(""" SELECT id, title, description FROM clash ORDER BY created_at  limit %s; """, (limit,))
        return cur.fetchall()
    
def get_related_clashes(clash_id, limit=5):
    with get_db_cursor() as cur:
        cur.execute(""" SELECT DISTINCT c.id, c.title, c.description, c.created_at
                        FROM clash c
                        JOIN clash_tag ct ON c.id = ct.clash_id
                        WHERE ct.tag_id IN (
                            SELECT tag_id FROM clash_tag WHERE clash_id = %s
                        )
                        AND c.id != %s
                        ORDER BY c.created_at DESC
                        LIMIT %s; """, (clash_id, clash_id, limit,))
        return cur.fetchall()
    
def arg_check_delete_status(arg_id):
    with get_db_cursor() as cur:
        cur.execute(""" SELECT is_deleted from arguments where id=%s """, (arg_id,))
        return cur.fetchone()
