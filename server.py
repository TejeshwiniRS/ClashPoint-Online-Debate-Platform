import os
from flask import Flask, render_template, redirect, url_for, session, abort, request
from authlib.integrations.flask_client import OAuth
from urllib.parse import urlencode, quote_plus
from dotenv import load_dotenv
import db   


load_dotenv()

app = Flask(__name__)
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

    replies_dict = {}
    for rep in replies:
        replies_dict.setdefault(rep["parent_id"], []).append(rep)
    for arg in arguments:
        print(type(arg), arg)
        arg["replies"] = replies_dict.get(arg["id"], [])
    return render_template("clash_view.html", clash=clash, arguments=arguments, user=user)

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
    print(user)
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

    return redirect(url_for("view_clash", clash_id=clash_id))

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
    
    # Now you can use these values to insert into the database, etc.
    return redirect(url_for("index"))

@app.route("/create_community")
def create_community():
    return render_template("create_community.html")

@app.route("/create_community_code")
def create_community_code():
    return render_template("create_community_code.html")

if __name__ == "__main__":
    app.run(debug=True)