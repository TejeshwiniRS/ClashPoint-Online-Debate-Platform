# ClashPoint - Online Debate Platform 
An online debate platform where you create clashes, argue your side, and let the community decide. 

App Link: https://clashpoint.up.railway.app

## Key Features

* Implemented a client-side toxicity moderator using TensorFlow.js to evaluate user input in real time.
* Built a recommended clashes engine to suggest related arguments based on shared tags.
* Developed a daily cron job to automatically close arguments reaching their end date.
* Designed a scoring algorithm that calculates argument scores based on vote distributions.

## Third-Party Integrations

* **TensorFlow.js** — Runs a lightweight ML toxicity model directly in the browser to flag offensive language before submission.
* **Auth0** — Handles user authentication and authorization including Google sign-in and secure session management.
* **Flask-Mail** — Used to send contact form submissions and notifications via SMTP.

## Running Locally

### Prerequisites
- Python 3.11+
- Pipenv
- PostgreSQL database

### Steps

1. **Clone the repo**
```bash
   git clone https://github.com/reshmaraoch/ClashPoint-Online-Debate-Platform.git
   cd ClashPoint-Online-Debate-Platform
```

2. **Install dependencies**
```bash
   pipenv install
```

3. **Set up environment variables**

   Create a `.env` file in the root folder:
```
   DATABASE_URL=postgresql://your_db_url_here
   FLASK_SECRET=your_secret_key
   AUTH0_CLIENT_ID=your_auth0_client_id
   AUTH0_CLIENT_SECRET=your_auth0_client_secret
   AUTH0_DOMAIN=your_auth0_domain
```

4. **Set up the database**
```bash
   psql $DATABASE_URL -f schema.sql
```

5. **Run the app**
```bash
   pipenv run flask --app server run
```

6. **Visit the app**

   Open your browser at `http://127.0.0.1:5000`

## Details:

**Toxicity Moderator** — TensorFlow.js runs a lightweight ML model in the browser, analyzing user input in real time and flagging toxic content before submission.

**Related Clashes** — Tag-based similarity engine fetches and displays clashes with overlapping topics to improve engagement and content discovery.

**Daily Cron Job** — Scheduled background task that runs every night at 11:55 PM to automatically close arguments once their end date is reached.

**Scoring Algorithm** — Weighted formula that dynamically updates each argument's score based on upvotes and downvotes to reflect community consensus.

