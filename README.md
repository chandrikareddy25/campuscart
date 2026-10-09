# CampusCart — application starter

A real React + FastAPI + PostgreSQL application for a master's CI/CD project.
This ZIP contains the application stage. Kubernetes manifests, GitHub Actions,
Argo CD deployment configuration, monitoring dashboards, and alerts will be
added in subsequent stages. It is not yet the complete CI/CD pipeline.

## Start on Windows 11 / Ubuntu WSL

Extract the ZIP into a new folder inside Ubuntu, such as ~/campuscart-starter.
Do not overwrite an existing project or database configuration.
Open the extracted campuscart folder in VS Code using `code .`.
Keep Docker Desktop running and use the Ubuntu integrated terminal.

```bash
bash scripts/setup.sh
docker compose up -d --build
docker compose ps
```

Storefront: http://localhost:8080
API documentation: http://localhost:8000/docs
Readiness: http://localhost:8000/health/ready
Prometheus metrics: http://localhost:8000/metrics

Open the storefront, add products, enter a name, and place an order.
Prices are in INR. No payments are collected. Accounts and authentication
are outside this starter's scope. It is intended for local college demos.

## Verify persistence

After placing an order:

```bash
docker compose exec db psql -U campuscart -d campuscart -c 'SELECT id,total,created_at FROM orders;'
docker compose restart
docker compose exec db psql -U campuscart -d campuscart -c 'SELECT id,total,created_at FROM orders;'
```

The order remains stored. Named-volume data persists through normal `down`/`up`.
Do not use `docker compose down -v` unless you intentionally want to delete data.
The SQL initialization script runs only on first initialization of the volume;
later schema changes require migrations rather than editing it alone.

## Backend checks

```bash
docker compose exec backend python -m unittest discover -s app -p 'test_*.py' -v
curl -fsS http://localhost:8000/health/ready
curl -fsS http://localhost:8000/api/products
```

## Development

Edit the source in VS Code. Rebuild changed application images:

```bash
docker compose up -d --build
```

Frontend hot reload, if Node.js is installed in Ubuntu:

```bash
cd frontend
npm install
npm run dev
```

Keep the Compose backend running. Vite proxies /api requests to localhost:8000.
Dependencies use version ranges for this first startup. Before building CI,
generate and commit a frontend lockfile and pin Python dependencies after the
first verified build. Container tags also need pinning for reproducible CI.

## Troubleshooting

```bash
docker compose logs --tail=80 backend db frontend
```

If port 8000 or 8080 is occupied, stop the old project or adjust the host-side
port in compose.yaml. Never share the generated .env file; Git ignores it.

## Implementation

- Nginx serves React and proxies API requests; no browser CORS configuration needed.
- Server calculates totals from database prices, never trusting browser prices.
- PostgreSQL row locks and a transaction prevent partial orders and overselling.
- Product locks are taken in ID order to avoid conflicting lock order.
- Input validation rejects duplicate products, empty names, and invalid quantities.
- Application metrics expose request counts, latency, and successful order counts.
- Separate liveness and database readiness endpoints support future Kubernetes probes.
- Database has no host port; app access is bound to loopback for local use.

## Validation status

Python syntax and unit checks can be run in the delivery workspace. Docker is
unavailable there, so container builds, frontend dependency resolution, and
database integration must be verified on your laptop before the next stage.
