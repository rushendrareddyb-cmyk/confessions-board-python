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

## Privacy, Abuse Prevention, and Accountability

The goal of this project is to allow anonymous participation while preventing spam and abuse without unnecessarily storing identifying information.

### How the design works

- **Device-based rate limiting:** Requests use the `X-Device-Id` header. The design uses a salted hash for rate-limit keys rather than using the raw device identifier as the key. Redis stores temporary counters with an expiry.
- **Preventing duplicate votes:** Redis uses an expiring `SET NX EX` marker to prevent a device from repeatedly voting on the same post.
- **Content moderation:** Posts that match blocked terms are held for review instead of being published immediately.
- **Community reporting:** Published posts can be reported. Once the required threshold is reached, a post can return to the moderation queue.
- **Human review:** Moderators can approve or reject held posts using the moderation API.
- **Separation of responsibilities:** PostgreSQL stores the application's persistent data, while Redis supports temporary rate limits, vote tracking, and live vote counts.

### Why this approach matters

Anonymity should not mean that abuse goes unchecked. Rate limits, vote restrictions, content filtering, community reporting, and human moderation provide safeguards without requiring users to create personal profiles.

The system still has limitations. A device identifier is not proof of a person's real-world identity, and users may try to bypass device-based restrictions. Moderation thresholds can also produce false positives or false negatives. The design therefore combines automated checks with moderator decisions rather than relying on a single control.

The objective is to minimize the collection of identifying information while keeping the service usable, fair, and resistant to abuse.
---

## Getting unstuck

| Symptom | Almost always |
|---|---|
| `/health` says `postgres: false` | Wrong hostname. In compose the host is the **service name**, not `localhost`. |
| Page will not load, logs fine | No `ports:` mapping, or bound to `127.0.0.1` not `0.0.0.0`. |
| `relation "..." does not exist` | Migrations did not run, or the app started before they finished. |
| Build takes minutes each time | `COPY . .` is above your dependency install. |
| CI cannot reach the database | In CircleCI service containers the host **is** `localhost` — opposite of compose. |


## Kubernetes Deployment and Verification

The project has three Kubernetes namespaces in the local Minikube cluster:

- `qa` — QA environment
- `stage` — staging environment
- `prod` — production namespace in the local cluster

### Apply the environment manifests

From the repository root, apply the manifest for the environment you intend to update:

```powershell
kubectl apply -f .\k8s\qa.yaml
kubectl apply -f .\k8s\stage.yaml
kubectl apply -f .\k8s\prod.yaml
```

Apply these individually and verify each rollout before moving to the next environment.

### Verify deployments

```powershell
kubectl get pods -n qa
kubectl get deployments -n qa

kubectl get pods -n stage
kubectl get deployments -n stage

kubectl get pods -n prod
kubectl get deployments -n prod
```

The application, PostgreSQL, and Redis deployments should be ready. Database migration jobs may show `Completed`, which is expected after a successful migration.

### Verify the health endpoint

Port-forward the service to a local port. Run the appropriate command in a separate terminal and keep it running during testing:

```powershell
kubectl port-forward -n qa svc/confessions-board 8080:80
```

Then test the endpoint:

```powershell
Invoke-RestMethod http://localhost:8080/health
Invoke-RestMethod "http://localhost:8080/posts?limit=5"
```

The health response should report `status: ok`, with PostgreSQL and Redis connectivity set to `true`.

Use separate local ports when testing multiple environments simultaneously.

### PostgreSQL rollout strategy

The PostgreSQL Deployments use the `Recreate` strategy to prevent the old database pod from overlapping with its replacement during a Deployment rollout. A replacement can cause a temporary interruption while PostgreSQL starts.

The web application uses readiness and liveness probes against `/health`. The current configuration uses a 3-second timeout, a 10-second readiness initial delay, and a 30-second liveness initial delay.

**Environment note:** `prod` refers to the Production namespace in the local Minikube cluster. It is not a separate external production server.

## CI/CD Pipeline


CircleCI is used for continuous integration. The repository contains its pipeline configuration at `.circleci/config.yml`.

The project pipeline is intended to validate code quality, run unit and integration tests, scan for accidentally committed secrets, and build the application image.

The latest pipeline runs checked for the PostgreSQL deployment-strategy pull request and its merge into `staging` completed successfully, as verified in CircleCI.

**Note:** Pipeline status can change with later commits. Check CircleCI for the current status before merging changes or submitting the project.