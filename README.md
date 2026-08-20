# UET NET MASTER

UET NET MASTER is a full-stack quiz and study platform for students, focused on computer networking and information technology subjects. It combines server-side quiz grading, persistent learning progress, Google Gemini AI assistance, and a cyberpunk-inspired web interface.

The current application interface is in Vietnamese.

## Project Highlights

- Built a REST API with FastAPI and asynchronous MongoDB access.
- Implemented account registration, login, token validation, and role-based admin access.
- Moved quiz grading to the server to reduce client-side score manipulation.
- Added AI-powered answer explanations, study recommendations, and exam-behavior analysis with Google Gemini.
- Built Flashcard, Practice, Wrong Question Bank, and Dashboard workflows for continuous learning.
- Added question-bank administration with search, filtering, create, edit, delete, and subject management.
- Added Docker and Render deployment configurations.
- Implemented browser activity monitoring and security-event logging for quiz sessions.

## Features

### Student Experience

- Sign up and sign in with student ID, name, and password.
- Take multiple-choice and short-answer quizzes with a 45-minute exam timer.
- Review submitted answers and receive AI explanations with memory tips.
- Study with flashcards or practice mode with immediate feedback.
- Automatically save incorrect questions for later review.
- Track quiz history, study streaks, accuracy, and learning progress.
- Use Cyberpunk, Midnight, or Hacker visual themes.
- Answer multiple-choice questions with `A/B/C/D` or `1/2/3/4` keyboard shortcuts.

### Admin Experience

- Authenticate with a server-validated Admin Key.
- Search and filter the question bank by subject or question text.
- Create, update, and delete multiple-choice or short-answer questions.
- Create new subjects and import/export question data as JSON.

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript, Tailwind CSS CDN |
| Backend | Python, FastAPI, Uvicorn, Gunicorn |
| Database | MongoDB Atlas, Motor, PyMongo |
| AI | Google Gemini API |
| Authentication | Salted SHA-256 password hashes and HMAC session tokens |
| Deployment | Docker and Render |

## Architecture

```text
+-------------------+       REST API        +-------------------+
| Browser           | <-------------------> | FastAPI           |
| index.html        |                       | main.py           |
+-------------------+                       +---------+---------+
                                                    |
                              +---------------------+---------------------+
                              |                                           |
                       +------+-------+                           +-------+-------+
                       | MongoDB      |                           | Gemini AI     |
                       | quizdb       |                           | explanations  |
                       | users        |                           | analysis      |
                       | questions    |                           +---------------+
                       | results      |
                       | user_data    |
                       +--------------+
```

The frontend is served by FastAPI at `/`. The backend exposes REST endpoints for authentication, questions, grading, progress persistence, AI features, monitoring, and administration.

## Getting Started

### Requirements

- Python 3.11 or newer.
- MongoDB Atlas or another accessible MongoDB server.
- A Google Gemini API key.

### 1. Install dependencies

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
MONGO_URI=mongodb+srv://<username>:<password>@<cluster>/<database>
GEMINI_API_KEY=<your-gemini-api-key>
ADMIN_KEY=<long-random-admin-key>
AES_SECRET_KEY=<long-random-token-secret>
ALLOWED_ORIGINS=http://localhost:8000
```

`MONGO_URI`, `GEMINI_API_KEY`, `ADMIN_KEY`, and `AES_SECRET_KEY` are required. Never commit `.env` or expose real credentials in a public repository.

### 3. Run the application

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

Interactive API documentation is available at:

- [Swagger UI](http://localhost:8000/docs)
- [ReDoc](http://localhost:8000/redoc)

## Deployment

### Docker

```bash
docker build -t uet-net-master .
docker run --rm -p 8000:8000 --env-file .env uet-net-master
```

### Render

The repository includes `render.yaml` for Render deployment. The service uses:

- Python 3.11.9
- `pip install -r requirements.txt` as the build command
- Gunicorn with a Uvicorn worker as the start command
- Render's `$PORT` environment variable

Configure `MONGO_URI`, `GEMINI_API_KEY`, `ADMIN_KEY`, `AES_SECRET_KEY`, and `ALLOWED_ORIGINS` in the Render dashboard. Set `ALLOWED_ORIGINS` to the deployed frontend origin.

## Data Model

The application uses the `quizdb` MongoDB database with these main collections:

- `users`: accounts, password hashes, salts, and roles.
- `questions`: question text, options, answers, subjects, and question types.
- `user_data`: dashboard data, incorrect questions, and spaced-repetition data.
- `results`: quiz scores, history, and completion status.
- `choices`, `logs`, and `security_logs`: quiz activity and monitoring records.

A multiple-choice question uses a zero-based answer index:

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

## Security Notes

- Passwords are stored as salted SHA-256 hashes.
- User and admin sessions use separate HMAC-signed tokens with expiration times.
- Quiz results are graded and associated with the authenticated student on the server.
- CORS origins can be restricted through `ALLOWED_ORIGINS`.
- Browser monitoring records suspicious events, but it is not a replacement for dedicated proctoring hardware or software.
- Rotate all credentials immediately if they are exposed.

## Project Structure

```text
.
|-- index.html          # Frontend application
|-- main.py             # FastAPI application and REST API
|-- updatequestions.py  # MongoDB question-data maintenance script
|-- requirements.txt    # Python dependencies
|-- Dockerfile          # Container configuration
|-- render.yaml         # Render deployment configuration
`-- README.md           # Project documentation
```

## License

This project does not currently include a separate license file. Add a `LICENSE` file before public distribution if you want to define how others may use the code.

## Author

Created as a learning and portfolio project for quiz-based study and AI-assisted learning.

