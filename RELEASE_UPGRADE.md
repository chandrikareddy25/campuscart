# CampusCart transaction-aware release guard

This patch contains only a replacement CI workflow and new release scripts/policy.
No frontend, backend application, database schema, or Kubernetes manifest replacement is included.

## What it does

- Tests the known working release and captures hashes of existing business rows before deployment.
- Builds both images, commits their tags, and waits for that exact Git revision and complete rollout.
- Uses the frontend's HTTP proxy to test student login, catalog, checkout, repeated checkout with the same request key, inventory/slot reservation, unpaid billing, and repeated cancellation.
- Compares full existing order, order-item, payment, and inventory records before/after deployment and rollback. Test-account orders are excluded; other business records are included.
- On confirmed verification failure, commits BOTH approved image tags back to Git. Argo CD reconciles that commit with automatic sync remaining enabled.
- Confirms readiness and repeats transaction checks after restoration. A rejected release stays a red Actions run even when recovery succeeds.
- Saves a JSON evidence artifact. Health-only mode is available through Actions > Run workflow for comparison, and cannot promote an unverified rollback baseline.
- Keeps the schema compatibility fingerprint and refuses a release when migration SQL differs. This is an explicit same-schema policy, not automatic database rollback.

## Installation order

1. Extract this patch and merge its contents into ~/campuscart/campuscart. Replace .github/workflows/ci.yaml; add scripts/, release/, and this file. Do not push yet.
2. In that folder, run `python3 scripts/prepare_release_test.py`. Enter a NEW dedicated test password (12–128 characters). It creates only release-test@campuscart.local, a visibly labelled test product, and a dedicated pickup desk. Re-running resets only this marked test account's password.
3. GitHub repository > Settings > Secrets and variables > Actions > New repository secret: name RELEASE_TEST_PASSWORD, value the test password.
4. Repository Settings > Actions > Runners > New self-hosted runner. Select Linux and x64. Run GitHub's displayed download/extraction/configuration commands in a NEW folder such as ~/campuscart-runner, not inside the source repository. During configuration, add the custom label campuscart. Keep GitHub's short-lived registration token private.
5. Run `./run.sh` in the runner folder. Leave this terminal running while workflows execute. Runner must use the same Ubuntu user that owns the kubeconfig. Python3, git and Linux kubectl must be on PATH. The scripts default to ~/.kube/campuscart.config; KUBECONFIG can override this.
6. In a second Ubuntu terminal in the project, run the checks:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
read -r -s -p 'Test password: ' RELEASE_TEST_PASSWORD; echo
export RELEASE_TEST_PASSWORD
python3 scripts/release_guard.py --preflight
unset RELEASE_TEST_PASSWORD
```

Preflight must print a JSON object containing four record hashes. It creates and cancels one test order; it never records an actual or simulated payment.
7. Add `release-results/` to .gitignore if missing. Pull latest Git changes before committing. Commit and push the patch:

```bash
git pull --ff-only
git add .github/workflows/ci.yaml scripts release RELEASE_UPGRADE.md .gitignore
git commit -m 'Add transaction-aware release verification and GitOps restoration'
git push
```

Expected first run: test, two builds, preflight, manifest update, verification; green result and release-evidence artifact. On success the bot commits the verified baseline policy. Pull that commit before subsequent work.

## Boundaries and interpretation

- Keep Docker Desktop, Kind, Ubuntu and the self-hosted runner running. Browser tabs and port-forward terminals are not needed by the guard.
- This is a local experiment environment. Run without other student/admin operations, because legitimate concurrent mutations can change record hashes.
- Synthetic cancelled orders and notifications remain as an audit trail and count in your since-startup order metric/analytics. No real payments are collected and no production records are deleted.
- Billing coverage validates the unpaid invoice and protects EXISTING payment rows. It does not automate cash receipt, UPI settlement, or full paid collection.
- The guard exercises backend APIs through nginx; it does not test React rendering or browser interactions.
- Network/runner errors produce INCONCLUSIVE evidence and do not trigger speculative rollback. Confirmed HTTP/transaction errors and readiness timeouts reject a release.
- Automatic image restoration cannot repair corrupt data. If hashes differ after rollback, the report says recovery_failed and requires investigation.
- A failed cancellation can leave a dedicated test order. Preflight then blocks the next release. Inspect and cancel that order instead of silently deleting it.
- Keep the repository controlled. The runner executes main-branch code and has cluster access. Pull requests run only tests/builds on hosted runners, without this runner or its test secret.
- Runner registration must be enabled in your repository settings. If a job stays queued, check runner status/label before changing the application.
- Migration changes require deliberate compatibility review and a new approved baseline; do not edit the fingerprint merely to bypass the guard.
- Bootstrap policy points to the current f15e33b release. Successful preflight establishes its transactional suitability. Never substitute older pre-billing images.

## Controlled experiments (after the healthy run passes)

Use the same release and hardware in each comparison, with no concurrent shoppers.

1. Record a healthy transactional run and download its JSON evidence.
2. Commit one controlled fault with `python3 scripts/inject_release_fault.py checkout-500` (or wrong-total). Review git diff before committing. This intentionally breaks checkout in the demo environment until automatic restoration completes.
3. Push the fault. Readiness remains healthy; transactional verification should reject it, restore BOTH known-good tags through Git, and validate recovery.
4. Revert the fault SOURCE commit with git revert, pull all bot commits first, and push. This builds a corrected release. An image restoration commit does not revert source code.
5. Repeat separately with wrong-total, then repeat each condition at least three times.
6. For the health-only comparison, introduce the same source fault and start Actions > Run workflow > verification_mode=health. Its report can pass despite a broken transaction; this is the baseline's blind spot. A push run defaults to transactional and may already restore the fault first, but the manual run rebuilds/redeploys the faulty source for the comparison.
7. After health-only testing, restore BOTH manifest tags from release/known-good.json and revert the source fault in the same recovery commit. Do not leave the bad health-only release running. The next deployment requires manifest tags to match the verified baseline. For initial experiments, ask for the exact recovery commands based on the current git log.

For the first fault test, use transactional mode only. We will inspect its artifact before attempting health-only comparisons.

## Measurements

CI workflow time is GitHub's full run duration. `wait_to_healthy_seconds` starts when the guard starts, and includes GitOps observation/rollout waiting; it is NOT commit-to-healthy latency. `total_guard_seconds` includes verification/restoration. `rollback_to_ready_seconds` begins immediately before the restoration commit and ends after the expected release is ready. Probe duration is separate. Save original reports, run IDs and commits; calculate mean/range only after collecting repeated observations. Do not compare these times directly to differently defined literature measurements.

## Validation performed before delivery

Eight controller tests cover promotion, health-only baseline isolation, paired restoration, newer-commit protection, inconclusive handling, migration-policy rejection, data corruption, and manifest preservation. The uploaded application's ten unit tests passed. An integration test against the uploaded API with a PostgreSQL-compatible PGlite engine and SQL adapter verified real checkout/cancellation SQL, preservation of an existing paid order, wrong-total rejection, HTTP 500 after order commit cleanup, and invalid-login rejection. HTTP was routed through a TestClient adapter in this environment. Kubernetes, nginx networking, GitHub credentials and live Git pushes require the first local healthy run; they were not exercised here.
