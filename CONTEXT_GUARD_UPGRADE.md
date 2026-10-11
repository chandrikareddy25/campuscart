# Transaction-state-aware verification upgrade

Merge the patch into the existing project. Replace the included scripts and CI workflow; no backend/frontend application, database migration, Kubernetes manifest or known-good policy is replaced.

## Install and first healthy run

1. Ensure the last fault source commit has been reverted and its recovery workflow is green.
2. Merge the patch files, then run `python3 -m unittest discover -s scripts -p 'test_*.py' -v` (20 tests).
3. Run `python3 scripts/prepare_release_test.py` again. Enter the SAME test password already stored as RELEASE_TEST_PASSWORD. This adds the dedicated control product and control pickup desk. It resets only the marked test account's password. If you choose another password, update the GitHub secret too.
4. Keep the self-hosted runner terminal listening. Pull the newest bot commit before committing:

```bash
cd ~/campuscart/campuscart
git pull --ff-only
git add scripts .github/workflows/ci.yaml CONTEXT_GUARD_UPGRADE.md
git commit -m "Add transaction-state-aware release verification"
git push
```

5. Download the new release-evidence artifact. The first healthy run should say mode=contextual, status=passed and decision.action=accept. Upload that report before starting experiments.

## Three comparison approaches

- health: current Kubernetes readiness and complete rollout checks.
- transactional: the EXACT earlier probe saved as transaction_probe_legacy.py; its successful/failed/inconclusive decisions remain the baseline.
- contextual (default): structured failure evidence, independent fixture/dependency observations, valid-path controls, bounded retries and explicit deferral.

Only passed transactional/contextual runs promote known-good tags. The migration compatibility fingerprint, newer-commit protection and paired Git-based restoration remain.

## Contextual behaviour

- Valid primary inventory and capacity: use the usual checkout, idempotency, billing, cancellation and row-integrity checks.
- Primary stock unavailable: use the separately marked control product. For active zero-stock inventory, first require HTTP 409 from an invalid checkout and verify no order was inserted; then require successful valid control checkout.
- Primary pickup capacity unavailable: require HTTP 409 for a full primary slot, then test an available control pickup slot. No valid control means DEFER, never accept.
- Incorrect total/invariants or unexpected checkout HTTP 500 with ready dependency: reject and restore approved image tags.
- Dependency readiness false, HTTP 429/502/503/504, or observation errors: retry twice (five seconds between attempts) only after checking for unfinished test orders. Unresolved evidence means DEFER.
- Authentication 401/403: defer for investigation rather than asserting release attribution. This can defer genuine authentication defects and must count as unresolved in the evaluation.
- Known conflicts: defer only if independent DB state supports the constraint; an unexplained 409 rejects. HTTP status alone does not establish business correctness.
- Data mismatches still reject. An image rollback cannot repair data; failed data-integrity recovery stays recovery_failed.

A deferred Actions run is RED, records status=deferred, does not promote the policy, and does not perform a speculative rollback. The candidate has ALREADY been deployed; deferral does not pause traffic or restore the old image. Investigate and explicitly restore the known-good manifest if required. This design is for the local experiment environment; it is not a progressive traffic canary.

## Real local benchmark: healthy release and business constraints

After the first contextual workflow passes, avoid shoppers/admin writes. Keep the runner/cluster running. Wait five minutes after other test logins before a benchmark and between benchmark repetitions, to respect the application's existing login rate limit. Do not disable that limit.

```bash
cd ~/campuscart/campuscart
python3 scripts/benchmark_context.py
```

Enter the test password. It directly executes all three checks against the SAME deployed release and uses REAL HTTP through nginx. Scenarios: healthy fixtures, primary stock unavailable, primary slots full, both constraints. Only dedicated test fixture stock/booked counters are temporarily changed; their initial values are restored in finally. Capacity fullness is deliberately injected test state, not generated shopper orders. This is a controlled fault/condition experiment on the real application.

Requires empty primary test slots and available control stock/slots. Synthetic cancelled orders/notifications remain. Run without concurrency; interruptions or a killed pod can prevent finally cleanup, so inspect test fixtures if a benchmark fails. The test password goes through stdin, not arguments or output.

The benchmark writes release-results/context-benchmark.json and prints each approach's result. Expected on the healthy release:

| Scenario | Health | Existing probe | Contextual probe |
|---|---|---|---|
| Healthy | passed | passed | passed |
| Primary stock unavailable | passed | failed | passed through verified control |
| Primary slots full | passed | failed | passed through verified control |
| Both constraints | passed | failed | passed through verified control |

These are actual probe outcomes. Mapping the old probe failure to a rollback follows its recorded policy; the benchmark itself performs NO Git commits, deployments or rollbacks. Do not claim it measured actual baseline rollback time. Workflow report comparative_decisions is only policy interpretation; the standalone benchmark provides the measured probes.

Existing two checkout-500 trials and one wrong-total trial remain baseline evidence. After the healthy/context benchmark, conduct the same release-defect tests under contextual mode and a combined business-constraint-plus-defect test. Do not introduce new fault variants or many repetitions until the first results are reviewed.

## Fixed research scope and fair evaluation

Question: Does explicit transaction-state evidence reduce unnecessary rollback decisions without increasing missed defects in this low-traffic application?

Compare all approaches on healthy, business-constraint, release-defect, transient-dependency and combined conditions. Report accept/reject/defer separately. A deferred defect is NOT a detected defect or successful recovery. Report missed defects, false rollback decisions, deferred-case rate and resolution latency; this prevents claiming improvement by simply refusing decisions. Two retries alone may explain an improvement: compare a retry-only policy with the contextual policy on the same trace as an ablation. Do not label temporal coincidence as proved root cause.

The benchmark changes dedicated fixture state only. Keep existing business rows/hash evidence, original report files, ground-truth labels and timing definitions. Separate policy replay, actual HTTP verification and end-to-end automated deployment/rollback evidence. Synthetic calls do not establish production traffic representativeness or statistical superiority. Three repetitions are preliminary evidence, not a universal guarantee.

No changes to website features, payment processing, database schema or cluster architecture are required.

## Verification before delivery

20 policy/controller tests passed. API integration using the uploaded backend with a PostgreSQL-compatible PGlite engine and SQL adapter passed checkout, idempotency, unpaid billing, cancellation, existing paid-record preservation, lost-response cleanup, stock fallback, full-capacity fallback, combined constraints, correct HTTP 409 rejection and a checkout defect alongside stock exhaustion. HTTP used a TestClient adapter here. Live Kubernetes/runner integration still requires the first healthy run and uploaded evidence.
