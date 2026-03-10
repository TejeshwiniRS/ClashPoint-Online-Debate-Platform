# ClashPoint - Online Debate Platform 
A structured debate platform designed to encourage meaningful discussions instead of chaotic comment sections.

ClashPoint allows users to create debates, post arguments, respond to opposing viewpoints, and vote on the most compelling ideas. By organizing conversations into structured threads and enforcing respectful communication through toxicity detection, the platform promotes thoughtful and constructive dialogue.


App Link: https://clashpoint.up.railway.app


## Motivation

Most online discussions today occur in unstructured comment sections on social media platforms. These environments often suffer from:

- Disorganized discussions
- Repeated arguments
- Toxic interactions
- Lack of visibility for high-quality contributions

ClashPoint aims to solve these issues by introducing **structured debates** where arguments are organized, evaluated, and moderated through community participation.

Instead of endless comment chains, users engage in **focused debates ("Clashes")** where ideas can be clearly presented, challenged, and voted upon.

---

## Features

### 1. Structured Debates (Clashes)

Clashes are the core component of the platform.

Each clash contains:
- Title and description
- Debate topic
- Tags
- Start and end time
- Argument threads

Users can join a clash and present arguments either supporting or opposing the topic. This structure ensures discussions remain focused and organized.

---

### 2. Threaded Argument System

Arguments can be posted within a clash and replied to by other users.

This creates hierarchical discussion threads where:
- Users respond directly to specific arguments
- Debate chains remain easy to follow
- Context is preserved across replies

Threaded discussions make complex debates easier to navigate.

---

### 3. Voting and Argument Scoring

Users can vote on arguments using upvotes and downvotes.

The platform includes a **custom scoring algorithm** that calculates argument scores based on vote distributions. This helps surface the most compelling arguments and creates a community-driven ranking system.

Highly scored arguments gain better visibility within debates.

---

### 4. Communities

ClashPoint supports topic-based communities where users can create and participate in debates around shared interests. Can join the community only suing the secret key shared by the admin.

Communities allow users to:
- Follow specific topics
- Discover new clashes
- Engage with like-minded participants

This helps organize discussions across different domains.

---

### 5. Toxicity Detection

To maintain respectful discussions, ClashPoint includes a **client-side toxicity moderation system built with TensorFlow.js**.

User input is evaluated in real time before submission. If toxic language is detected, the user is warned before posting.

This helps reduce abusive interactions and encourages constructive debate.

---

### 6. Recommended Clashes

The platform includes a **recommended clashes engine** that suggests related debates based on shared tags.

This helps users:
- Discover relevant discussions
- Explore similar debate topics
- Engage with communities aligned with their interests

---

### 7. Automatic Clash Closure

Clashes have a defined end date.

A **daily cron job automatically closes clashes** that reach their end date, preventing additional arguments and preserving the final state of the debate.

---

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

## Core Details:

**Toxicity Moderator** — TensorFlow.js runs a lightweight ML model in the browser, analyzing user input in real time and flagging toxic content before submission.

**Related Clashes** — Tag-based similarity engine fetches and displays clashes with overlapping topics to improve engagement and content discovery.

**Daily Cron Job** — Scheduled background task that runs every night at 11:55 PM to automatically close arguments once their end date is reached.

**Scoring Algorithm** — Weighted formula that dynamically updates each argument's score based on upvotes and downvotes to reflect community consensus.

