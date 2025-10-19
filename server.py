import os
from flask import Flask, render_template, redirect, url_for, session, abort, request, flash, jsonify
from authlib.integrations.flask_client import OAuth
from urllib.parse import urlencode, quote_plus
from dotenv import load_dotenv
import db
from datetime import datetime
from flask_mail import Mail, Message
import secrets
import string
import base64

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
@app.route("/clashes")
def clashes():
    user_id = current_user_id()
    scope = request.args.get("scope", "all")
    page = int(request.args.get("page", 1))
    query = request.args.get("query", "").strip()
    sort_by = request.args.get("sort")
    status = request.args.get("status")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    category = request.args.get("category")

    limit = 6
    offset = (page - 1) * limit

    if scope == "mine" and user_id:
        clashes, total = db.search_clashes(
            query, sort_by, status, start_date, end_date, limit, offset,
            category=category, owner_id=user_id
        )
    else:
        clashes, total = db.search_clashes(
            query, sort_by, status, start_date, end_date, limit, offset, category
        )

    total_pages = (total + limit - 1) // limit
    tags = db.get_all_tags()

    return render_template(
        "clashes.html",
        clashes=clashes,
        page=page,
        total_pages=total_pages,
        tags=tags,
        selected_category=category,
        query=query,
        sort_by=sort_by,
        status=status,
        start_date=start_date,
        end_date=end_date,
        scope=scope
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

    return redirect(url_for("clashes"))

@app.route("/logout")
def logout():
    session.clear()
    params = {
        "returnTo": url_for("clashes", _external=True),
        "client_id": os.environ.get("AUTH0_CLIENT_ID")
    }
    return redirect(f"https://{os.environ.get('AUTH0_DOMAIN')}/v2/logout?" + urlencode(params, quote_via=quote_plus))

# ---------- Static Pages ----------
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
    tags = db.get_all_tags() 
    return render_template("create_clash.html")

@app.post("/new_clash")
def new_clash():
    owner_id = current_user_id()
    title = request.form.get("title")
    description = request.form.get("description")
    tag_id = request.form.get("tags")

    # user wants to add a new tag. 
    new_tag = request.form.get("newTag")
    if new_tag:
        tag_id = db.add_new_tag(new_tag)
        # how can I make this new tag, the tag that pairs with the new clash???
        # come back to this. 
        # make it so that the function returns the new id of the tag. 
    
    clash_close_date = request.form.get("close_date")
    clash_close_date = datetime.strptime(clash_close_date, "%Y-%m-%d")
    new_clash_id = db.add_clash(owner_id, title, description, clash_close_date)
    db.add_clash_tag(tag_id, new_clash_id)
    # where do I redirect after this? 
    return redirect(url_for("clashes"))

@app.route("/create_community")
def create_community():
    return render_template("create_community.html")

@app.post("/new_community")
def new_community():
    owner_id = current_user_id()
    title = request.form.get("title")
    description = request.form.get("description")
    community_close_date = request.form.get("close_date")
    community_close_date = datetime.strptime(community_close_date, "%Y-%m-%d")

    # Generating and Encoding the community code

    options = string.ascii_letters + string.digits
    code = ''.join(secrets.choice(options) for _ in range(7))
    encoded_code = base64.b64encode(code.encode()).decode()

    db.add_community(community_close_date, title, description, encoded_code, owner_id)
    return render_template("create_community.html", code = code)

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
        return redirect(url_for("clashes"))

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
    return redirect(url_for("clashes"))

@app.route("/communities")
def communities():
    user_id = current_user_id()
    scope = request.args.get("scope", "all")  # all | mine
    query = request.args.get("query", "").strip()
    status = request.args.get("status")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if scope == "mine" and user_id:
        communities = db.search_communities(query, status, start_date, end_date, user_id=user_id)
    else:
        communities = db.search_communities(query, status, start_date, end_date)

    user_community_ids = db.get_user_community_ids(user_id) if user_id else []
    return render_template("communities.html",
                           communities=communities,
                           user_community_ids=user_community_ids,
                           query=query, status=status,
                           start_date=start_date, end_date=end_date,
                           scope=scope)

# To Join a community
@app.post("/join_community/<int:community_id>")
def join_community(community_id):
    user_id = current_user_id()
    if not user_id:
        flash("Please log in to join a community.", "error")
        return redirect(url_for("login"))

    entered_code = request.form.get("secret_code", "").strip()
    if not entered_code:
        flash("Please enter the community code.", "error")
        return redirect(url_for("communities"))

    # --- Check if already a member ---
    joined_ids = db.get_user_community_ids(user_id)
    if community_id in joined_ids:
        flash("You are already a member of this community.", "info")
        return redirect(url_for("communities"))

    # --- Fetch and verify only that community's code ---
    is_valid = db.verify_community_code(community_id, entered_code)
    if not is_valid:
        flash("Invalid code for this community.", "error")
        return redirect(url_for("communities"))

    # --- If valid, add membership ---
    db.add_user_to_community(user_id, community_id)
    flash("Welcome! You've successfully joined the community.", "success")
    return redirect(url_for("communities"))



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

# ---------- Community Views ----------
@app.route("/community/<int:community_id>")
def view_community(community_id):
    print("came here")
    user_id = current_user_id()
    community = db.get_community_details(community_id)
    if not community:
        abort(404)

    members = db.get_community_members(community_id)
    clashes = db.get_clashes_by_community(community_id)
    is_owner = (user_id == community["owner_id"])

    return render_template(
        "community_view.html",
        community=community,
        members=members,
        clashes=clashes,
        is_owner=is_owner,
        user=current_user_info()
    )

@app.get("/community/<int:community_id>/search_clashes")
def search_community_clashes(community_id):
    query = request.args.get("query", "").strip()
    results = db.search_clashes_in_community(community_id, query)
    return jsonify(results)

@app.post("/community/<int:community_id>/remove_member")
def remove_member(community_id):
    user_id = current_user_id()
    if not user_id:
        abort(401)
    community = db.get_community_details(community_id)
    if not community or community["owner_id"] != user_id:
        abort(403)

    email = request.form.get("email", "").strip()
    if not email:
        flash("Please enter an email address.", "error")
        return redirect(url_for("view_community", community_id=community_id))
    
    success = db.remove_community_member(community_id, email)
    if success:
        flash(f"Removed member with email: {email}", "success")
    else:
        flash("No member found with that email.", "error")

    return redirect(url_for("view_community", community_id=community_id))
    


if __name__ == "__main__":
    app.run(debug=True)
