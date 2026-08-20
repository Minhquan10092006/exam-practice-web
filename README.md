# UET NET MASTER

UET NET MASTER is an online quiz and study platform designed for students, with a focus on computer networking and information technology subjects. The application combines a MongoDB question bank, a cyberpunk browser interface, user authentication, learning progress tracking, and Google Gemini AI features.

> Interface language: Vietnamese
> Backend: FastAPI
> Database: MongoDB
> AI provider: Google Gemini

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Local Setup](#local-setup)
- [Environment Variables](#environment-variables)
- [MongoDB Data Model](#mongodb-data-model)
- [Main API Endpoints](#main-api-endpoints)
- [Question Bank Administration](#question-bank-administration)
- [Docker](#docker)
- [Render Deployment](#render-deployment)
- [Operations and Security](#operations-and-security)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

### Student Features

- Sign up and sign in with student ID (MSV), full name, and password.
- Automatic sign-in using a session token valid for 7 days.
- Select subjects from the list stored in MongoDB.
- Take multiple-choice and short-answer quizzes.
- A 45-minute time limit for each quiz.
- Server-side grading, so scoring does not depend on frontend logic.
- Review each question, the correct answer, and the submitted answer.
- Ask Gemini AI to explain questions, answers, and memory tips.
- Flashcard mode for quick review.
- Practice mode with immediate feedback and no exam pressure.
- Automatically save incorrect answers to the Wrong Question Bank.
- Review incorrect questions as dedicated flashcards.
- Dashboard with quiz count, result history, study streak, and learning statistics.
- AI-generated study analysis and recommendations for improving performance.
- Browser activity monitoring for events such as leaving the tab, copy/paste actions, right-clicks, and DevTools access.
- Three visual themes: Cyberpunk, Midnight, and Hacker.
- Keyboard shortcuts using `A/B/C/D` or `1/2/3/4` for multiple-choice questions.

### Admin Features

- Sign in with an Admin Key and receive a separate admin token.
- View, filter, and search the question bank.
- Create, edit, and delete questions.
- Support for `multiple_choice` and `short_answer` questions.
- Create new subjects.
- Import and export question data as JSON from the admin interface.

## Architecture

```text
Browser (index.html)
        |
        | REST API /api/*
        v
FastAPI (main.py)
   |                 |
   |                 +--> Google Gemini AI
   |
   +--> MongoDB Atlas
        - users
        - user_data
        - questions
        - results
        - choices
        - logs
        - security_logs
```

The frontend is a standalone HTML file using Tailwind CSS through its CDN and plain JavaScript. The backend serves `index.html` at `/` and provides REST APIs for authentication, questions, grading, progress persistence, AI features, and administration.

## Requirements

- Python 3.11 or newer.
- MongoDB Atlas or another MongoDB server accessible by the application.
- A Google Gemini API key.
- Internet access for package installation, frontend CDN assets, and Gemini API requests.

## Local Setup

### 1. Open the project

```bash
git clone <your-repository-url>
cd quiz-web
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create `.env`

Create `.env` in the project root using the example in [Environment Variables](#environment-variables). Never commit this file to Git.

### 5. Start the development server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

FastAPI also provides interactive API documentation:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Production-style local command

```bash
gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120
```

## Environment Variables

| Variable | Required | Description |
|---|---:|---|
| `MONGO_URI` | Yes | MongoDB connection string. The application uses the `quizdb` database. |
| `GEMINI_API_KEY` | Yes | API key for answer explanations and AI analysis. |
| `ADMIN_KEY` | Yes | Key used to sign in to the administration area. |
| `AES_SECRET_KEY` | Yes | Secret used to sign HMAC user session tokens. |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins. Defaults to `http://localhost:8000`. |
| `PORT` | No | Port used when starting with `python main.py`. Defaults to `8000`. |
| `RENDER` | No | Identifies the Render environment and disables local DNS overrides. |
| `AES_IV` | No | Legacy configuration variable; the current version does not read it. |

Example with placeholders only:

```env
MONGO_URI=mongodb+srv://<username>:<password>@<cluster>/<database>
GEMINI_API_KEY=<your-gemini-api-key>
ADMIN_KEY=<long-random-admin-key>
AES_SECRET_KEY=<long-random-token-secret>
ALLOWED_ORIGINS=http://localhost:8000
```

The application exits during startup if a required variable is missing. Restart the server after changing `.env`.

## MongoDB Data Model

The default database name is `quizdb`.

### `questions`

A multiple-choice question looks like this:

```json
{
  "q_id": "network_001",
  "q": "Question text",
  "options": ["Answer A", "Answer B", "Answer C", "Answer D"],
  "answer": 1,
  "subject": "network",
  "type": "multiple_choice"
}
```

`answer` is a zero-based index. A short-answer question stores its answer in `ans`:

```json
{
  "q_id": "network_fill_001",
  "q": "Which layer does TCP operate at?",
  "options": [],
  "ans": "Transport",
  "subject": "network",
  "type": "short_answer"
}
```

Other collections include:

- `users`: accounts, password hashes, salts, and roles.
- `user_data`: dashboard data, incorrect questions, and spaced-repetition data for each MSV.
- `results`: quiz results and completion or disqualification status.
- `choices`: submitted choices during a quiz.
- `logs`: monitoring heartbeat records.
- `security_logs`: suspicious activity and security-breach records.

## Main API Endpoints

### Authentication and User Data

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/signup` | Create a new account. |
| `POST` | `/api/auth/login` | Sign in with MSV and password. |
| `GET` | `/api/auth/me?token=...` | Validate a user session token. |
| `GET` | `/api/user-data/{msv}?token=...` | Read the current user's learning data. |
| `PUT` | `/api/user-data/{msv}` | Save dashboard, incorrect-question, and study data. |

### Learning and Quizzes

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/subjects` | Return available subjects. |
| `GET` | `/api/questions/{subject}?token=...` | Return up to 1,000 questions for a subject. |
| `POST` | `/api/grade-quiz` | Grade a quiz server-side and save the result. |
| `POST` | `/api/get-answers` | Return answers for review; requires a token. |
| `POST` | `/api/submit-choice` | Save a student's selected answer. |
| `GET` | `/api/dashboard/{msv}?token=...` | Return quiz statistics and history. |

### AI and Monitoring

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/explain` | Explain a question using Gemini. |
| `POST` | `/api/analyze-dashboard` | Analyze progress and provide study recommendations. |
| `POST` | `/api/analyze-integrity` | Analyze quiz behavior with AI. |
| `POST` | `/api/heartbeat` | Record monitoring heartbeat data. |
| `POST` | `/api/security-breach` | Record a violation and mark a result as `DISQUALIFIED`. |

### Admin

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/admin/login` | Exchange the Admin Key for a temporary admin token. |
| `GET` | `/api/admin/questions` | Filter and search questions. |
| `POST` | `/api/admin/question` | Create a question. |
| `PUT` | `/api/admin/question/{question_id}` | Update a question. |
| `DELETE` | `/api/admin/question/{question_id}` | Delete a question. |
| `POST` | `/api/admin/subjects` | Create a subject using a placeholder question. |

Token placement varies by endpoint: some endpoints use a query parameter, while others expect it in the request body. Check `/docs` for the exact request schema when integrating another client.

## Question Bank Administration

1. Open the application and go to the `Admin` tab.
2. Enter the value of `ADMIN_KEY`.
3. Search or filter questions by subject.
4. Use the create, edit, and delete actions to manage the question bank.
5. Export the JSON data before making large changes so that you have a backup.

The `updatequestions.py` script assigns the `network` subject to questions that do not have a `subject` field:

```powershell
$env:MONGO_URI = "<your-mongodb-uri>"
python updatequestions.py
```

This script directly modifies MongoDB. Back up the `questions` collection before running it against production data.

## Docker

Build the image:

```bash
docker build -t uet-net-master .
```

Run the container:

```bash
docker run --rm -p 8000:8000 --env-file .env uet-net-master
```

Then open [http://localhost:8000](http://localhost:8000). The Dockerfile uses Python 3.12 Alpine and starts the application with Uvicorn.

## Render Deployment

The project includes `render.yaml` with the following web-service configuration:

- Build command: `pip install -r requirements.txt`
- Start command: Gunicorn with a Uvicorn worker
- Python version: `3.11.9`
- Port: supplied by Render through `$PORT`

Configure these secrets in Render Environment Variables:

```text
MONGO_URI
GEMINI_API_KEY
ADMIN_KEY
AES_SECRET_KEY
ALLOWED_ORIGINS
```

The current `render.yaml` marks some variables as secrets, but `ADMIN_KEY` and `ALLOWED_ORIGINS` may need to be added manually if they are not already configured. For production, set `ALLOWED_ORIGINS` to the real frontend origin, for example:

```text
https://your-app.onrender.com
```

## Operations and Security

- Never commit `.env`, MongoDB URIs, Gemini API keys, Admin Keys, or token secrets to GitHub.
- Rotate any secret immediately if it has been exposed.
- Use long, randomly generated values for `ADMIN_KEY` and `AES_SECRET_KEY`.
- Restrict `ALLOWED_ORIGINS` to the required frontend origins in production.
- Use a MongoDB database user with the minimum required permissions and restrict network access.
- Server-side grading reduces frontend tampering, but browser-based monitoring is not a replacement for a dedicated proctoring system.
- Back up `questions`, `users`, `user_data`, and `results` before large administrative operations.
- Short-answer results are currently returned for manual review; automatic normalization and matching is not implemented in the same way as multiple-choice grading.

## Troubleshooting

### `Thiếu MONGO_URI trong file .env!`

Check that `.env` is in the project root and that `MONGO_URI` contains a valid connection string. Make sure your machine or server IP is allowed in MongoDB Atlas.

### `Thiếu GEMINI_API_KEY trong file .env!`

Create or regenerate a Gemini API key, set `GEMINI_API_KEY`, and restart the server.

### MongoDB cannot be reached locally

When running locally, the application configures DNS servers `8.8.8.8` and `8.8.4.4` to support MongoDB SRV URIs. Check your firewall, Internet connection, and cluster permissions if the issue continues.

### CORS errors after deployment

Set `ALLOWED_ORIGINS` to the exact frontend origin, without a trailing slash, and restart the service.

### No questions appear for a subject

Check the `quizdb.questions` collection, especially the `subject` field. Run `updatequestions.py` if older records do not have a subject.

## License

This project does not currently include a separate license file. Add a `LICENSE` file if the project will be publicly distributed or used by others.

## Author

This project was created for learning and quiz-practice purposes.

![Quân's GitHub stats](https://github-readme-stats.vercel.app/api?username=Minhquan10092006&show_icons=true&theme=radical)
![Top Langs](https://github-readme-stats.vercel.app/api/top-langs/?username=Minhquan10092006&layout=compact)
