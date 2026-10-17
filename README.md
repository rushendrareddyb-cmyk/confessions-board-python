# Campus Confessions Board

**Language:** Python (FastAPI) &nbsp;|&nbsp; **Needs:** Postgres + Redis

This is a **starter**. The application already works. Your job is everything
that gets it building, tested and running in CI.

---

## You do not need Python installed

You will build this into a container, and the container brings its own
Python 3.12. You are not being asked to extend the app — you are being asked
to ship it.

---
 i want to add few things
## 1. What this app needs

| | |
|---|---|
| **Runtime** | Python 3.12 |
| **Install dependencies** | `pip install -r requirements.txt` |
| **Start the app** | `uvicorn app.main:app --host 0.0.0.0 --port 8080` |
| **Listens on** | port 8080, bound to `0.0.0.0` |
| **Environment variables** | `DATABASE_URL`, `REDIS_URL` |
| **Needs running first** | Postgres, Redis, and the migrations applied |

### What it does

Anonymous posts, voting and comments. Anything that trips the word filter is held for a moderator instead of going live, enough reports pull a published post back into the queue, and one person cannot flood the board.

### Endpoints

```
GET  /health
POST /posts                     header X-Device-Id, {"body":"..."}
GET  /posts                     the published board, live scores
GET  /posts/{id}                one post with its comments
POST /posts/{id}/vote           header X-Device-Id, {"direction":"up"}
POST /posts/{id}/report         header X-Device-Id
POST /posts/{id}/comments       header X-Device-Id, {"body":"..."}
GET  /moderation/queue          what is held, and why
POST /moderation/{id}           {"action":"approve"} or {"action":"reject"}
```

`/health` reports Postgres and Redis **separately**. If it says
`postgres: false` the app started fine and your compose wiring is wrong —
do not go looking in the application code.

### Migrations

`migrations/` holds `.sql` files applied **in filename order** before the app
starts. They create the tables and insert sample data. A container running
`psql` over them in order is enough; you do not need a migration tool.

---



## 2. What you must write

| File | What it has to do |
|---|---|
| `Dockerfile` | Install dependencies **before** copying source, pin the base image, do not run as root. |
| `docker-compose.yml` | App + Postgres + Redis + a migration step, one `docker compose up`. |
| `.circleci/config.yml` | lint → unit tests → integration tests → secret scan → image build |
| Unit tests | For `app/moderation.py`. No database, no network. |
| Integration tests | Against a real Postgres and Redis as CircleCI service containers. |

Then push your image to **your own Docker Hub account**, tagged `:1.0`.

### When it works

```bash
docker compose up --build
curl localhost:8080/health
```

```json
{"status":"ok","postgres":true,"redis":true}
```

---

## Where the marks are

`app/moderation.py` is **pure logic** — plain functions over plain data, no
database and no HTTP. Start your tests there. Use pytest:
`pytest --cov=app --cov-report=term-missing`. Minimum 70%.

Start with `find_blocked`. Feed it `stupid`, `STUPID`, `stup1d`, `$tupid`, `stuuupid` and `s.t.u.p.i.d` - all six must be caught. Then feed it `classmate`, `assignment`, `analysis` and `dumbbell`... and decide for yourself whether the last one should pass. Then `check_rate` at the three boundaries, and `reports_needed` either side of every multiple of the divisor - 9, 10, 11.

## Why Redis is here

Redis holds everything that would otherwise identify somebody. The rate-limit counter is keyed on a salted hash of the device, in a key that expires with the window. The 'already voted' marker is a `SET NX EX` on another salted hash - it proves a vote happened without recording who, and it evaporates on its own. Live vote counts sit there too, warmed from Postgres on a cold cache. Postgres keeps only the words.

## The hard part

Anonymous but not unaccountable. You must stop abuse without storing anything that identifies who wrote what.

Write your answer in your README. It is worth more marks than the feature.

---

## Getting unstuck

| Symptom | Almost always |
|---|---|
| `/health` says `postgres: false` | Wrong hostname. In compose the host is the **service name**, not `localhost`. |
| Page will not load, logs fine | No `ports:` mapping, or bound to `127.0.0.1` not `0.0.0.0`. |
| `relation "..." does not exist` | Migrations did not run, or the app started before they finished. |
| Build takes minutes each time | `COPY . .` is above your dependency install. |
| CI cannot reach the database | In CircleCI service containers the host **is** `localhost` — opposite of compose. |

## CI/CD Pipeline

This project uses CircleCI for Continuous Integration (CI).

- Automatically runs the build pipeline when changes are pushed to GitHub.
- Installs the required Python dependencies.
- Checks Python files for syntax errors.

**Status:** CircleCI pipeline testing in progress.
