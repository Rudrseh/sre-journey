# sre-journey

# python-k8s-app

A three-tier app — **React frontend → Flask backend → PostgreSQL database** — containerized with Docker,
pushed to Docker Hub, and deployed to Kubernetes with a fully automated CI/CD pipeline.

```
Browser
   │
   ▼
┌─────────────────────┐
│  React (nginx)       │  react-frontend-service (LoadBalancer, external)
│  static SPA          │
└──────────┬───────────┘
           │ /api/* proxied internally by nginx
           ▼
┌─────────────────────┐
│  Flask backend        │  python-backend-service (ClusterIP, internal only)
│  gunicorn + SQLAlchemy│
└──────────┬───────────┘
           │
           ▼
┌─────────────────────┐
│  PostgreSQL            │  postgres-service (ClusterIP, internal only)
│  backed by a PVC        │  — data survives pod restarts/crashes
└─────────────────────┘
```

The browser only ever talks to the frontend. nginx inside the frontend container proxies `/api/*`
requests to the backend Service over the cluster's internal network — so there's no CORS
configuration to worry about, and the backend/database are never exposed outside the cluster.

## Project layout
```
python-k8s-app/
├── backend/
│   ├── app.py                 # Flask API: /, /health, /info, /api/items (CRUD)
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── Dockerfile
│   ├── .dockerignore
│   └── tests/test_app.py
├── frontend/
│   ├── src/App.jsx            # Items UI: add / list / delete
│   ├── src/App.css
│   ├── package.json
│   ├── vite.config.js         # dev-server proxy to localhost:5000
│   ├── Dockerfile             # multi-stage: node build → nginx serve
│   ├── nginx.conf             # serves the SPA + proxies /api to the backend
│   └── .dockerignore
├── k8s/
│   ├── configmap.yaml         # non-sensitive config (incl. DB host/port/name)
│   ├── secret.example.yaml    # TEMPLATE for API_KEY / DB_USER / DB_PASSWORD
│   ├── postgres-pvc.yaml      # persistent volume claim for DB data
│   ├── postgres-deployment.yaml
│   ├── postgres-service.yaml
│   ├── backend-deployment.yaml
│   ├── backend-service.yaml
│   ├── frontend-deployment.yaml
│   └── frontend-service.yaml
├── .github/workflows/ci-cd.yml
└── .gitignore
```

## 1. Run it locally (optional sanity check)

You need a local Postgres for the backend to talk to. Easiest way, with Docker:
```bash
docker run --rm -d --name local-postgres \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=appdb \
  -p 5432:5432 postgres:16-alpine
```

**Backend:**
```bash
cd backend
pip install -r requirements.txt
DB_HOST=localhost DB_USER=postgres DB_PASSWORD=postgres DB_NAME=appdb python app.py
# API now at http://localhost:5000
```

**Frontend** (in a second terminal):
```bash
cd frontend
npm install
npm run dev
# visit http://localhost:5173 — Vite proxies /api to localhost:5000 automatically
```

## 2. Build the Docker images
```bash
docker build -t <YOUR_DOCKERHUB_USERNAME>/python-k8s-backend:1.0.0 ./backend
docker build -t <YOUR_DOCKERHUB_USERNAME>/python-k8s-frontend:1.0.0 ./frontend
```

## 3. Push the images to Docker Hub
```bash
docker login
docker push <YOUR_DOCKERHUB_USERNAME>/python-k8s-backend:1.0.0
docker push <YOUR_DOCKERHUB_USERNAME>/python-k8s-frontend:1.0.0
```

## 4. Update the manifests with your image names
In `k8s/backend-deployment.yaml` and `k8s/frontend-deployment.yaml`, replace
`<YOUR_DOCKERHUB_USERNAME>` in the `image:` line with your actual Docker Hub username.

## 5. Config variables & secrets

Both the ConfigMap and Secret are shared across all three tiers (Postgres reads some of the same
keys the backend does, so the two are guaranteed to agree).

- **`k8s/configmap.yaml`** — non-sensitive: `APP_ENV`, `LOG_LEVEL`, `APP_NAME`, `FEATURE_GREETING`,
  and DB connection info that isn't secret: `DB_HOST`, `DB_PORT`, `DB_NAME`.
- **`k8s/secret.example.yaml`** — a **template** for `API_KEY`, `DB_USER`, `DB_PASSWORD`, with
  placeholder text. Never put real values in a file that gets committed.

```bash
kubectl apply -f k8s/configmap.yaml

cp k8s/secret.example.yaml k8s/secret.yaml
# edit k8s/secret.yaml with real values — this file is gitignored, it will not be committed
kubectl apply -f k8s/secret.yaml
```

⚠️ A Kubernetes `Secret` is base64-*encoded*, not encrypted. That's fine for local learning; for
real production secrets, use a proper secret manager (Sealed Secrets, External Secrets Operator,
or your cloud provider's secret manager) instead.

## 6. Deploy to Kubernetes

Order matters here: Postgres needs to exist before the backend starts (the backend's
`initContainer` will wait for it, but there's no point applying it before the ConfigMap/Secret
it depends on).

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml            # your real one, not secret.example.yaml

kubectl apply -f k8s/postgres-pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/postgres-service.yaml
kubectl rollout status deployment/postgres

kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
kubectl rollout status deployment/python-backend

kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml
kubectl rollout status deployment/react-frontend
```

Check status any time:
```bash
kubectl get pods
kubectl get pvc                # should show postgres-pvc as Bound
kubectl get svc
```

## 7. Access the app

- **Cloud cluster (EKS/GKE/AKS)** with `LoadBalancer` support:
  ```bash
  kubectl get svc react-frontend-service
  ```
  then visit `http://<EXTERNAL-IP>/`.

- **Local cluster (minikube/kind)**, where `LoadBalancer` won't get an external IP:
  ```bash
  minikube service react-frontend-service
  # or:
  kubectl port-forward svc/react-frontend-service 8080:80
  # then visit http://localhost:8080
  ```

You should see the Items UI. Add an item, refresh the page — it's still there, because it's
sitting in Postgres, not in the frontend's memory.

## 8. Prove the data survives a database failure

This is the actual point of the PVC — verify it, don't just take it on faith.

```bash
# 1. Add an item through the UI (or via curl) so there's something to lose.
curl -X POST http://localhost:8080/api/items \
  -H "Content-Type: application/json" \
  -d '{"name":"Survives a crash","description":"proving the PVC works"}'

# 2. Confirm it's there.
curl http://localhost:8080/api/items

# 3. Kill the Postgres pod outright — simulates a crash, OOM-kill, or node failure.
kubectl delete pod -l app=postgres

# 4. Kubernetes schedules a replacement pod automatically. Watch it come back:
kubectl get pods -l app=postgres -w
# Ctrl+C once it shows Running/1/1 Ready

# 5. Check the data again — same item, same id, because the PVC was reattached
#    to the new pod rather than starting from an empty volume.
curl http://localhost:8080/api/items
```

If you instead ran Postgres with `emptyDir` or no volume at all, step 5 would come back empty —
that's the difference the PVC makes.

**What would actually lose data:** deleting the PVC itself (`kubectl delete pvc postgres-pvc`) or
the PersistentVolume it's bound to. Pod deletion, node drains, and normal rollouts are all safe;
PVC/PV deletion is the one operation that isn't.

## 9. Update / redeploy after a code change
```bash
docker build -t <YOUR_DOCKERHUB_USERNAME>/python-k8s-backend:1.1.0 ./backend
docker push <YOUR_DOCKERHUB_USERNAME>/python-k8s-backend:1.1.0
# update the image tag in k8s/backend-deployment.yaml, then:
kubectl apply -f k8s/backend-deployment.yaml
kubectl rollout status deployment/python-backend
```
Same pattern for the frontend, against `k8s/frontend-deployment.yaml`.

## Notes
- Both app containers run as non-root users; the backend uses `gunicorn` rather than Flask's dev server.
- The backend has an `initContainer` that blocks on `pg_isready` before the app starts, so pods
  don't crash-loop while Postgres is still booting on a fresh cluster.
- The Postgres Deployment uses `strategy: Recreate`, not the default `RollingUpdate` — its PVC is
  `ReadWriteOnce`, so only one pod can mount it at a time; `Recreate` kills the old pod before
  starting a new one, avoiding a stuck rollout.
- Always use a specific version tag (not just `latest`) in the deployment manifests for
  reproducible deployments — `latest` can silently change what gets pulled.

---

## CI/CD with GitHub Actions

The pipeline lives at `.github/workflows/ci-cd.yml` and has three jobs:

| Job | Runs on | When | What it does |
|---|---|---|---|
| `test` | GitHub cloud runner | every push & PR | spins up a real Postgres service container, runs backend `pytest` against it, then `npm ci && npm run build` for the frontend |
| `build-and-push` | GitHub cloud runner | push to `main` only | builds **both** images, tags each with the short git SHA + `latest`, pushes both to Docker Hub |
| `deploy` | **your own machine** (self-hosted runner) | after build-and-push succeeds | applies ConfigMap/Secret, then deploys Postgres → backend → frontend in order, waiting for each rollout before moving on |

### Why a self-hosted runner?
You're using minikube/kind, which only exists on your laptop. GitHub's cloud runners have no
network path to `localhost` on your machine, so they physically cannot run `kubectl apply` against
it. A **self-hosted runner** is the GitHub Actions agent running as a process on your own machine —
it has direct access to your local `kubectl` context, so the `deploy` job executes there instead
of in the cloud. `test` and `build-and-push` still run on GitHub's free cloud runners as normal.

### One-time setup

**1. Create the required GitHub secrets**
In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**
- `DOCKERHUB_USERNAME` — your Docker Hub username
- `DOCKERHUB_TOKEN` — a Docker Hub [access token](https://hub.docker.com/settings/security) (not your password)
- `APP_API_KEY` — real value for the app's `API_KEY`
- `APP_DB_USER` — real value for the Postgres username
- `APP_DB_PASSWORD` — real value for the Postgres password

The `deploy` job builds the Kubernetes Secret directly from these three on every run — the real
values only ever exist inside GitHub's encrypted secrets store and your cluster, never in the repo.

**2. Register a self-hosted runner on your machine**
In your GitHub repo: **Settings → Actions → Runners → New self-hosted runner**, pick your OS, and
run the commands it shows you, e.g. on Linux/macOS:
```bash
mkdir actions-runner && cd actions-runner
curl -o actions-runner.tar.gz -L https://github.com/actions/runner/releases/download/<version>/actions-runner-<os>-<version>.tar.gz
tar xzf actions-runner.tar.gz
./config.sh --url https://github.com/<you>/<repo> --token <token-shown-in-github-ui>
```

**3. Make sure that machine can already deploy manually**
Before starting the runner, confirm this works on that same machine:
```bash
minikube start        # or: kind create cluster
kubectl get nodes      # should show your local node as Ready
```
The runner uses whatever `kubectl` context is active on that machine — no kubeconfig secret
needed, since it's all local.

**4. Start the runner**
```bash
./run.sh
```
To keep it listening for jobs in the background (recommended), install it as a service instead:
```bash
sudo ./svc.sh install
sudo ./svc.sh start
```
Once running, it shows as "Idle" under **Settings → Actions → Runners** and automatically picks
up the `deploy` job whenever the pipeline runs.

### Triggering the pipeline
```bash
git add .
git commit -m "Update app"
git push origin main
```
Watch it run under the **Actions** tab of your GitHub repo. On success:
```bash
kubectl get pods
kubectl port-forward svc/react-frontend-service 8080:80
# visit http://localhost:8080
```

### Notes on this setup
- Each deploy is tagged with the 7-char git commit SHA (e.g. `a1b2c3d`), not `latest` — so every
  deployed image is traceable to an exact commit, and `imagePullPolicy: Always` in both deployment
  manifests ensures the new tag is actually pulled.
- Postgres itself isn't rebuilt or redeployed by the pipeline — it uses the stock `postgres:16-alpine`
  image and its manifests only change if you edit them by hand. Only the backend and frontend
  images change on every push.
- PRs run `test` only — nothing is built, pushed, or deployed until merged to `main`.
- If you later move to a real cloud cluster (EKS/GKE/AKS), you can retire the self-hosted runner:
  swap the `deploy` job's `runs-on: self-hosted` back to `runs-on: ubuntu-latest` and authenticate
  `kubectl` using a `KUBE_CONFIG` secret instead. At that point also reconsider Postgres itself —
  a managed database (RDS, Cloud SQL, etc.) is usually a better fit than running it in-cluster.
