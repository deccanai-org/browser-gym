# Jenkins CI/CD — CUA hub mock UIs (delta)

Pipelines for **jenkins-main.soulhq.ai** (or any Jenkins with `frontend-agent`).

## What gets deployed

| Job | Builds | Publishes to |
|---|---|---|
| `cua-hub-mocks-delta` | 5 gym mock SPAs (`dist/`) | `xmazon` / `xbay` / `xmail` / `xoogle-calendar` / `xber-eats` `.delta.deccanexperts.ai` |
| `cua-gym-seed-delta` | (no UI) re-seeds Postgres | `cua-gym` @ `10.0.141.72` |

**UI deploy ≠ seed deploy.** After projection/ambient changes, run **both** jobs (or seed manually with `python -m tools.seed_via_psql`).

## Prerequisites (DevOps)

1. **Agent** `frontend-agent` online (label `frontend`).
2. **Credentials** in Jenkins (same as other Deccan jobs):
   - `jenkins_user_bitbucket` — clone `deccan-ai/cua-gym-hub` or gym repo
   - `cua-gym-pg` — Postgres password for `10.0.141.72` (seed job only)
3. **Deploy hook** — fill in `tools/deploy_hub_dist.sh` with how delta static sites are published (rsync / S3 / k8s). The pipeline calls that script after build.
4. **Job create permission** for whoever installs these (you currently see an empty dashboard — need **Job/Build** role).

## Install jobs (Jenkins admin)

### Option A — Pipeline from SCM (recommended)

1. New Item → **Pipeline** → name `cua-hub-mocks-delta`
2. Pipeline definition: **Pipeline script from SCM**
   - SCM: Git
   - URL: `https://bitbucket.org/deccan-ai/ecommerce-browser-gym.git` (or GitHub mirror)
   - Branch: `seed-to-cua-gym`
   - Script path: `ci/jenkins/cua-hub-mocks-delta.groovy`
3. Repeat for `cua-gym-seed-delta` → `ci/jenkins/cua-gym-seed-delta.groovy`

### Option B — Inline script (mirror only)

Copy the `.groovy` file body into the job’s **Pipeline script** field (same as Illusion `ci/jenkins/` mirrors).

## Developer workflow

```bash
# 1) Push UI work on gym branch
git push origin seed-to-cua-gym

# 2) (Optional) Mirror to Bitbucket hosting repo
git clone …/cua-gym-hub
./tools/push_to_hub.sh /path/to/cua-gym-hub
# commit + push shopgym-ui-update on cua-gym-hub

# 3) Jenkins → Build cua-hub-mocks-delta (parameter: delta)
# 4) Jenkins → Build cua-gym-seed-delta (after seed projection changes)
# 5) Smoke: open https://xmazon.delta.deccanexperts.ai/?sid=<from cua_task_sid_map>
```

## Build must use `build_hub_mocks.sh`

Never `npm run build` alone on delta — it bakes the wrong API base and drops product assets. The pipeline runs:

```bash
./tools/build_hub_mocks.sh . https://cua-gym-hub.delta.soulhq.ai
```

## Annotator platform (separate)

The **annotation platform** (`browser-gym-annotator`) is a different deploy unit (frontend + backend + Postgres). See `browser-gym-annotator/docs/DEPLOY.md`. Do not mix with cua-hub mock jobs unless you intentionally bundle them.
