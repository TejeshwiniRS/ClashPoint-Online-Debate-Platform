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
import os
import json

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
    # print(clash)
    if not clash:
        abort(404)

    arguments = db.get_arguments_by_clash_id(clash_id)
    replies = db.get_replies_by_clash_id(clash_id)
    trending_clashes = db.get_trending_clashes()
    related_clashes = db.get_related_clashes(clash_id)

    # Reply Nesting
    def reply_tree(all_replies):
        reply_dict = {}
        for r in all_replies:
            reply_dict.setdefault(r["parent_id"], []).append(r)

        def attach_child_reply(parent):
            reply_children = reply_dict.get(parent["id"], [])
            for reply_child in reply_children:
                reply_child["replies"] = attach_child_reply(reply_child)
            return reply_children
        return reply_dict, attach_child_reply

    reply_dict, attach_child = reply_tree(replies)
    for arg in arguments:
        arg["replies"] = attach_child(arg)
        # print(type(arg), arg)
        # print(arguments)
        # print(json.dumps(arguments, indent=2, default=str))
        # print(user)
    return render_template("clash_view.html", clash=clash, arguments=arguments, user=user_id, trending_clashes=trending_clashes, related_clashes=related_clashes)

@app.route('/clash/<int:clash_id>/post', methods=['POST'])
def post_argument(clash_id):
    user = current_user_id()
    if not user:
        abort(401)

    content = request.form.get("content", "").strip()
    argument_type = request.form.get("argument_type", "")
    parent_id = request.form.get("parent_id")

    if not content:
        abort(400, 'Content cannot be empty')
    # print(clash_id, user, content, argument_type, parent_id)
    db.create_argument(clash_id=clash_id, user_id=user, content=content, argument_type=argument_type, parent_id=parent_id)
    return redirect(url_for('view_clash', clash_id=clash_id))

@app.route("/argument/<int:arg_id>/vote", methods=["POST"])
def vote_argument(arg_id):
    user = current_user_id()
    if not user:
        abort(401)

    vote = request.form.get("vote")
    if vote not in ["up", "down"]:
        abort(400, "Invalid vote")
    value = 1 if vote == "up" else -1
    clash_id = db.vote_argument(arg_id, value)

    stats = db.get_score(arg_id)
    stats["score"] = 0.5 * stats["up_votes"] - stats["down_votes"]
    return jsonify({
        "success": True,
        "up_votes": stats["up_votes"],
        "down_votes": stats["down_votes"],
        "score": round(float(stats["score"]),2)
    })

    return redirect(url_for("view_clash", clash_id=clash_id))

@app.route("/argument/<int:arg_id>/edit", methods=["POST"])
def edit_argument(arg_id):
    user = current_user_id()
    if not user:
        abort(401)

    content = request.form.get("content", "").strip()
    if not content:
        return jsonify({"success": False, "error": "Content cannot be empty"}), 400

    clash_id = db.edit_argument(arg_id, content)
    if not clash_id:
        return jsonify({"success": False, "error": "Not found"}), 404

    return jsonify({"success": True, "content": content})


@app.route("/argument/<int:arg_id>/delete", methods=["POST"])
def delete_argument(arg_id):
    user_id = session.get("user_id")
    if not user_id:
        abort(401)

    clash_id = db.mark_argument_deleted(arg_id, user_id)
    if not clash_id:
        return jsonify({"success": False, "error": "Not allowed"}), 403

    return jsonify({"success": True})

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
    
    clash_close_date = request.form.get("close_date")
    clash_close_date = datetime.strptime(clash_close_date, "%Y-%m-%d")
    new_clash_id = db.add_clash(owner_id, title, description, clash_close_date)
    db.add_clash_tag(tag_id, new_clash_id)
    # where do I redirect after this? 
    return redirect(url_for("view_clash", clash_id=new_clash_id))

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
    options = string.ascii_letters + string.digits
    code = ''.join(secrets.choice(options) for _ in range(7))

    new_community_id = db.add_community(community_close_date, title, description, code, owner_id)
    return render_template("create_community.html", code = code, new_community_id = new_community_id)

@app.get("/edit/<int:community_id>")
def get_community_edit_page(community_id): 
    community = db.get_community_details(community_id)
    return render_template("edit_community.html", community = community)

@app.post("/edit_community/<int:community_id>")
def edit_community(community_id):
    owner_id = current_user_id()
    title = request.form.get("title")
    description = request.form.get("description")
    community_close_date = request.form.get("close_date")
    community_close_date = datetime.strptime(community_close_date, "%Y-%m-%d")
    db.update_community(community_id, title, description, community_close_date, owner_id)
                     
    return redirect(url_for('view_community', community_id = community_id))


@app.route("/create_community_clash/<int:community_id>")
def create_community_clash(community_id):
    tags = db.get_all_tags() 
    return render_template("create_community_clash.html", community_id=community_id)

@app.post("/new_community_clash/<int:community_id>")
def new_community_clash(community_id):
    owner_id = current_user_id()
    title = request.form.get("title")
    description = request.form.get("description")
    tag_id = request.form.get("tags")

    # user wants to add a new tag. 
    new_tag = request.form.get("newTag")
    if new_tag:
        tag_id = db.add_new_tag(new_tag)
    
    clash_close_date = request.form.get("close_date")
    clash_close_date = datetime.strptime(clash_close_date, "%Y-%m-%d")
    new_clash_id = db.add_community_clash(owner_id, title, description, clash_close_date, community_id)
    db.add_clash_tag(tag_id, new_clash_id)
    return redirect(url_for("view_clash", clash_id=new_clash_id))

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
    flash("Your account was deleted from ClashPoint", "success")
    return redirect(url_for("clashes"))

@app.route("/communities")
def communities():
    user_id = current_user_id()
    scope = request.args.get("scope", "all")
    query = request.args.get("query", "").strip()
    status = request.args.get("status")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    page = int(request.args.get("page", 1))
    limit = 6
    offset = (page - 1) * limit

    if scope == "mine" and user_id:
        communities, total = db.search_communities(
            query, status, start_date, end_date, user_id=user_id, limit=limit, offset=offset
        )
    else:
        communities, total = db.search_communities(
            query, status, start_date, end_date, limit=limit, offset=offset
        )

    total_pages = (total + limit - 1) // limit
    user_community_ids = db.get_user_community_ids(user_id) if user_id else []

    return render_template(
        "communities.html",
        communities=communities,
        user_community_ids=user_community_ids,
        query=query,
        status=status,
        start_date=start_date,
        end_date=end_date,
        scope=scope,
        page=page,
        total_pages=total_pages,
    )


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


    flash("Your account was deleted successfully from ClashPoint and Auth0.", "deleted")
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

# ---------- Community Views ----------
@app.route("/community/<int:community_id>")
def view_community(community_id):
    user_id = current_user_id()
    community = db.get_community_details(community_id)
    if not community:
        abort(404)

    # --- Pagination params ---
    page = int(request.args.get("page", 1))
    limit = 6
    offset = (page - 1) * limit

    # --- Members ---
    members = db.get_community_members(community_id)
    num_members = len(members)

    # --- Paginated clashes ---
    clashes, total = db.get_clashes_by_community(community_id, limit=limit, offset=offset)
    num_clashes = total
    total_pages = (total + limit - 1) // limit

    is_owner = (user_id == community["owner_id"])

    return render_template(
        "community_view.html",
        community=community,
        members=members,
        clashes=clashes,
        is_owner=is_owner,
        user=current_user_info(),
        num_members=num_members,
        num_clashes=num_clashes,
        page=page,
        total_pages=total_pages
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
