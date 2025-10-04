import os
from flask import Flask, render_template, redirect, url_for, session
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

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login():
    return auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )

@app.route("/signup")
def signup():
    return redirect(
        "https://" + os.environ["AUTH0_DOMAIN"] + "/authorize?"
        + urlencode({
            "response_type": "code",
            "client_id": os.environ["AUTH0_CLIENT_ID"],
            "redirect_uri": url_for("callback", _external=True),
            "scope": "openid profile email",
            "screen_hint": "signup"
        }))

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

if __name__ == "__main__":
    app.run(debug=True)
