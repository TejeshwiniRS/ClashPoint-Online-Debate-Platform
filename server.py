import os
from flask import Flask, render_template, redirect, url_for, session, abort, request, flash, jsonify
from authlib.integrations.flask_client import OAuth
from urllib.parse import urlencode, quote_plus
from dotenv import load_dotenv
import db
from datetime import datetime
from flask_mail import Mail, Message

# ---------------- Environment & Setup ----------------
load_dotenv()

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET")

db.setup()

# ---------------- OAuth (Auth0) ----------------
oauth = OAuth(app)
auth0 = oauth.register(
    "auth0",
    client_id=os.environ.get("AUTH0_CLIENT_ID"),
    client_secret=os.environ.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={"scope": "openid profile email"},
    server_metadata_url=f"https://{os.environ.get('AUTH0_DOMAIN')}/.well-known/openid-configuration"
)

# ---------------- Mail (Flask-Mail) ----------------
app.config.update(
    MAIL_SERVER=os.environ.get("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_PORT=int(os.environ.get("MAIL_PORT", 587)),
    MAIL_USE_TLS=os.environ.get("MAIL_USE_TLS", "true").lower() == "true",
    MAIL_USERNAME=os.environ.get("MAIL_USERNAME"),
    MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.environ.get("MAIL_DEFAULT_SENDER"),
)
mail = Mail(app)
CONTACT_RECIPIENTS = [
    e.strip() for e in os.environ.get("CONTACT_RECIPIENTS", "").split(",") if e.strip()
]

# ---------------- Utility Functions ----------------
@app.context_processor
def inject_tags():
    tags = db.get_all_tags()
    return dict(tags=tags)

def current_user_info():
    """Auth0 profile (name, email, picture, etc.)"""
    return session.get('user')

def current_user_id():
    """Internal numeric user id from DB"""
    return session.get('user_id')

def get_auth0_mgmt_token():
    """Fetch a short-lived Management API token using app credentials."""
    data = {
        "client_id": os.environ["AUTH0_CLIENT_ID"],
        "client_secret": os.environ["AUTH0_CLIENT_SECRET"],
        "audience": f"https://{os.environ['AUTH0_DOMAIN']}/api/v2/",
        "grant_type": "client_credentials"
    }
    resp = requests.post(f"https://{os.environ['AUTH0_DOMAIN']}/oauth/token", json=data)
    resp.raise_for_status()
    return resp.json()["access_token"]

# ---------------- Routes ----------------
@app.route("/")
@app.route("/index")
def index():
    page = int(request.args.get("page", 1))
    query = request.args.get("query", "").strip()
    sort_by = request.args.get("sort")
    status = request.args.get("status")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    category = request.args.get("category")

    limit = 6
    offset = (page - 1) * limit

    if category and (query or sort_by or status or (start_date and end_date)):
        clashes, total = db.search_clashes(query, sort_by, status, start_date, end_date, limit, offset, category)
    elif query or sort_by or status or (start_date and end_date):
        clashes, total = db.search_clashes(query, sort_by, status, start_date, end_date, limit, offset)
    elif category:
        clashes, total = db.get_clashes_by_tag(category, limit, offset)
    else:
        with db.get_db_cursor() as cur:
            cur.execute("""
                SELECT id, title, description, created_at, status
                FROM clash_dump
                WHERE owner_id IS NULL
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s;
            """, (limit, offset))
            clashes = [dict(row) for row in cur.fetchall()]
            cur.execute("SELECT COUNT(*) FROM clash_dump;")
            total = cur.fetchone()['count']

    total_pages = (total + limit - 1) // limit
    tags = db.get_all_tags()

    return render_template(
        "index.html",
        clashes=clashes,
        page=page,
        total_pages=total_pages,
        tags=tags,
        selected_category=category,
        query=query,
        sort_by=sort_by,
        status=status,
        start_date=start_date,
        end_date=end_date
    )

# ---------- Auth ----------
@app.route("/login")
def login():
    redirect_uri = url_for("callback", _external=True)
    return auth0.authorize_redirect(redirect_uri=redirect_uri)

@app.route("/signup")
def signup():
    redirect_uri = url_for("callback", _external=True)
    session.clear()
    return auth0.authorize_redirect(
        redirect_uri=redirect_uri,
        screen_hint="signup"
    )

@app.route("/callback")
def callback():
    token = auth0.authorize_access_token()
    user_info = token["userinfo"]

    auth0_id = user_info["sub"]
    email = user_info.get("email")

    username  = (user_info.get("username") or "").strip()
    nickname  = (user_info.get("nickname") or "").strip()
    full_name = (user_info.get("name") or "").strip()

    display_name = (
        username or
        nickname or
        full_name or
        (email.split("@")[0] if email else "User")
    )

    user_id = db.upsert_user(auth0_id, display_name, email)

    user_info["display_name"] = display_name
    session["user"] = user_info
    session["user_id"] = user_id

    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    params = {
        "returnTo": url_for("index", _external=True),
        "client_id": os.environ.get("AUTH0_CLIENT_ID")
    }
    return redirect(f"https://{os.environ.get('AUTH0_DOMAIN')}/v2/logout?" + urlencode(params, quote_via=quote_plus))

# ---------- Static Pages ----------
@app.route("/communities")
def communities():
    return render_template("communities.html")

@app.route("/terms")
def terms():
    return render_template("terms.html", now=datetime.utcnow)

# ---------- Contact ----------
@app.get("/contact")
def contact():
    user = current_user_info()
    prefill = {
        "username": (user or {}).get("display_name") or (user or {}).get("username")
                    or (user or {}).get("nickname") or (user or {}).get("name") or "",
        "email": (user or {}).get("email", "") if user else ""
    }
    return render_template("contact.html", prefill=prefill)

@app.post("/contact")
def contact_submit():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()

    if request.form.get("website"):
        return redirect(url_for("contact"))

    if not email or "@" not in email:
        flash("Please provide a valid email address.", "error")
        return redirect(url_for("contact"))
    if not subject or not message:
        flash("Subject and message are required.", "error")
        return redirect(url_for("contact"))

    full_subject = f"[ClashPoint Contact] {subject}"
    body = f"Username: {username or '(not provided)'}\nEmail: {email}\n\nMessage:\n{message}\n"

    try:
        msg = Message(subject=full_subject, recipients=CONTACT_RECIPIENTS, body=body)
        msg.reply_to = email
        mail.send(msg)
        flash("Thanks! Your message has been sent.", "success")
    except Exception:
        flash("Sorry, something went wrong while sending your message.", "error")

    return redirect(url_for("contact"))

# ---------- Clash Views ----------
@app.route('/clash/<int:clash_id>')
def view_clash(clash_id):
    user_id = current_user_id()
    clash = db.get_clash_details(clash_id)
    if not clash:
        abort(404)

    arguments = db.get_arguments_by_clash_id(clash_id)
    replies = db.get_replies_by_clash_id(clash_id)

    replies_dict = {}
    for rep in replies:
        replies_dict.setdefault(rep["parent_id"], []).append(rep)
    for arg in arguments:
        arg["replies"] = replies_dict.get(arg["id"], [])

    return render_template("clash_view.html", clash=clash, arguments=arguments, user=user_id)

@app.route('/clash/<int:clash_id>/post', methods=['POST'])
def post_argument(clash_id):
    user_id = current_user_id()
    if not user_id:
        abort(401)

    content = request.form.get("content", "").strip()
    argument_type = request.form.get("argument_type", "")
    parent_id = request.form.get("parent_id")

    if not content:
        abort(400, 'Content cannot be empty')

    db.create_argument(clash_id=clash_id, user_id=user_id, content=content, argument_type=argument_type, parent_id=parent_id)
    return redirect(url_for('view_clash', clash_id=clash_id))

@app.route("/argument/<int:arg_id>/vote", methods=["POST"])
def vote_argument(arg_id):
    user_id = current_user_id()
    if not user_id:
        abort(401)

    vote = request.form.get("vote")
    if vote not in ["up", "down"]:
        abort(400, "Invalid vote")
    value = 1 if vote == "up" else -1
    clash_id = db.vote_argument(arg_id, value)

    return redirect(url_for("view_clash", clash_id=clash_id))

# ---------- Create ----------
@app.route("/create_clash")
def create_clash():
    return render_template("create_clash.html")

@app.post("/new_clash")
def new_clash():
    owner_id = current_user_id()
    title = request.form.get("title")
    description = request.form.get("description")
    tags = request.form.getlist("tags")
    close_date = request.form.get("close_date")

    db.add_clash(owner_id, title, description, tags, close_date)
    return redirect(url_for("index"))

@app.route("/create_community")
def create_community():
    return render_template("create_community.html")

@app.route("/create_community_code")
def create_community_code():
    return render_template("create_community_code.html")

# ---------- Profile ----------
@app.route("/profile")
def profile():
    user = session.get("user")
    if not user:
        flash("Please log in to view your profile.", "error")
        return redirect(url_for("login"))
    return render_template("profile.html", user=user)

@app.post("/update_profile")
def update_profile():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))

    new_name = request.form.get("username", "").strip()
    if not new_name:
        flash("Username cannot be empty.", "error")
        return redirect(url_for("profile"))

    db.update_username(session["user_id"], new_name)
    session["user"]["display_name"] = new_name
    session["user"]["name"] = new_name
    flash("Username updated successfully!", "success")
    return redirect(url_for("profile"))

# ---------- Delete Account ----------
@app.post("/delete_account")
def delete_account():
    user_id = session.get("user_id")
    auth0_user = session.get("user", {}).get("sub")

    if not user_id:
        return redirect(url_for("index"))

    db.delete_user(user_id)

    try:
        token = get_auth0_mgmt_token()
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.delete(
            f"https://{os.environ['AUTH0_DOMAIN']}/api/v2/users/{auth0_user}",
            headers=headers,
            timeout=10
        )
        print(f"Auth0 delete response: {r.status_code} {r.text}")
    except Exception as e:
        print(f"⚠️ Error deleting from Auth0: {e}")

    session.clear()
    flash("Your account was deleted from ClashPoint and Auth0.", "success")
    return redirect(url_for("index"))

# ---------- Run ----------

# Cron Job to close the clashes
@app.route("/internal/close-expired", methods=["POST"])
def close_expired():
    secret = os.environ.get("CRON_SECRET")
    if secret and request.headers.get("X-CRON-SECRET") != secret:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    closed_clashes, closed_communities = db.close_expired_items()

    return jsonify({
        "ok": True,
        "closed_clashes": closed_clashes,
        "closed_communities": closed_communities
    })


if __name__ == "__main__":
    app.run(debug=True)
