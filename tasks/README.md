# Data-driven tasks

Drop a `*.json` file in **this** directory and the gym registers it at import:
brief, start path, seed world and verifier suite, no Python touched. The loader
is `server/tasks_json.py`; the schema and the check vocabulary are documented in
its module docstring and enforced by `tests/test_tasks_json.py`.

`examples/` is **not** scanned. Copy a file up one level to activate it.

## The short version

```
tasks/M401.json          -> registered as task "M401/gift_wrap_wrong_recipient"
tasks/examples/M401.json -> inert; a reference to copy from
```

Identity is three separate fields, never one fused string:

| field        | meaning                                       |
|--------------|-----------------------------------------------|
| `short_id`   | the `BRIEFS` key (`M401`)                     |
| `slug`       | the documentation half of the full id         |
| `category`   | `A`/`B`/`C`/`D`/`M`                           |
| `difficulty` | `easy`/`medium`/`hard`                        |

The full id is `short_id + "/" + slug`, derived by the loader.

## What fails at load, on purpose

Everything the affordance audit found *silently defaulting* is a hard error
here, because a task that half-loads is worse than one that does not load:

- an unknown check kind, op, collection, scalar, app or entity field
- a product `category` outside the storefront's seven (it would render but be
  unreachable from every nav, filter and category page)
- a missing `start_path` — write `"/"` explicitly if you mean root
- milestone weights that do not sum to 1.0
- a suite with no required and no forbidden milestone
- a forbidden milestone carrying weight
- an id that collides with a Python task (a JSON task never overrides one)
- any milestone that already fires against the untouched seed world

A tag that puts a product in no subcategory drill-down is a *warning*, not an
error — a few real tasks want exactly that.

## What a JSON task cannot express

Money arithmetic derived from other records, negation-aware claim detection
beyond `mail_body_affirms`, bus/scheduler truth, engine-derived expectations
(`quote()`), pairwise record joins, regex over free text, date reasoning, and
anything about the *trajectory* rather than the world. Those stay in Python.
The `python` check kind is the declared, allowlisted escape hatch — a hybrid
task that says so is honest, a silently-downgraded one is not.

## Oracles

`test_oracle_solvers_aligned` requires every registered task to have an oracle
solver. A JSON task supplies one with an optional `oracle` block:

```json
"oracle": [
  { "action": "goto",  "path": "/cart", "reasoning": "the candle is already here" },
  { "action": "click", "selector": "a[data-test-id='btn-proceed-checkout']" },
  { "action": "fill",  "selector": "input[data-test-id='input-qty']", "value": "1" },
  { "action": "select","selector": "select[data-test-id='select-variant']", "value": "v_x" }
]
```

Without it the task registers and runs, but the oracle-alignment test will name
it. That is deliberate: a stub solver would satisfy the coverage test while
proving nothing.
