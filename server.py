import os
from flask import Flask, render_template, redirect, url_for, session, abort, request, jsonify, flash
from authlib.integrations.flask_client import OAuth
from urllib.parse import urlencode, quote_plus
from dotenv import load_dotenv
import db   
import json


load_dotenv()

app = Flask(__name__, static_folder="static",static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET")

db.setup()

oauth = OAuth(app)
auth0 = oauth.register(
    "auth0",
    client_id=os.environ.get("AUTH0_CLIENT_ID"),
    client_secret=os.environ.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={"scope": "openid profile email"},
    server_metadata_url=f"https://{os.environ.get('AUTH0_DOMAIN')}/.well-known/openid-configuration"
)

@app.context_processor
def inject_tags():
    tags = db.get_all_tags()
    return dict(tags=tags)

def current_user():
    return session.get('user')

@app.route("/")
@app.route("/index")
def index():
    page = int(request.args.get("page", 1))
    category = request.args.get("category")
    limit = 6
    offset = (page - 1) * limit

    if category:
        clashes, total = db.get_clashes_by_tag(category, limit, offset)
    else:

        # Fetch clashes ordered by created_at DESC
        with db.get_db_cursor() as cur:
            cur.execute("""
                SELECT id, title, description, created_at, status
                FROM clash_dump
                WHERE owner_id is NULL
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
        selected_category=category
    )

@app.route("/login")
def login():
    redirect_uri = url_for("callback", _external=True)
    return auth0.authorize_redirect(redirect_uri=redirect_uri)

@app.route("/signup")
# def signup():
#     return redirect(
#         "https://" + os.environ["AUTH0_DOMAIN"] + "/authorize?"
#         + urlencode({
#             "response_type": "code",
#             "client_id": os.environ["AUTH0_CLIENT_ID"],
#             "redirect_uri": url_for("callback", _external=True),
#             "scope": "openid profile email",
#             "screen_hint": "signup"
#         }))
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
    name = user_info.get("name")
    email = user_info.get("email")

    user_id = db.upsert_user(auth0_id, name, email)
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

@app.route("/communities")
def communities():
    return render_template("communities.html")


@app.route("/terms")
def terms():
    return "<h1>Terms & Conditions</h1>"

@app.route("/contact")
def contact():
    return "<h1>Contact Us</h1>"

# @app.route('/')
# def index():
#     return render_template('base.html')


def current_user():
    return session.get('user_id')

@app.route('/clash/<int:clash_id>')
def view_clash(clash_id):
    user = current_user()
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
    return render_template("clash_view.html", clash=clash, arguments=arguments, user=user, trending_clashes=trending_clashes, related_clashes=related_clashes)

@app.route('/clash/<int:clash_id>/post', methods=['POST'])
def post_argument(clash_id):
    user = current_user()
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
    user = current_user()
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
    user = current_user()
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

# creating a clash
@app.route("/create_clash")
def create_clash():
    return render_template("create_clash.html")

@app.post("/new_clash")
def new_clash():
   
    owner_id = current_user()
    title = request.form.get("title")
    description = request.form.get("description")
    tags = request.form.getlist("tags")  # use getlist for multi-select
    close_date = request.form.get("close_date")

    db.add_clash(owner_id, title, description, tags, close_date)
    
    return redirect(url_for("index"))

@app.route("/create_community")
def create_community():
    return render_template("create_community.html")

@app.route("/create_community_code")
def create_community_code():
    return render_template("create_community_code.html")

if __name__ == "__main__":
    app.run(debug=True)