# Contributing

Thanks for considering a contribution to **polymarket-execution**.

## Workflow

All changes — features, fixes, docs, chores — go through pull requests. Direct pushes to `main` are blocked by branch protection.

### 1. Branch

Use a descriptive prefix:

| Prefix | Use for |
|---|---|
| `feat/<name>` | New feature or module |
| `fix/<name>` | Bug fix |
| `docs/<name>` | Documentation only |
| `refactor/<name>` | Refactor without behavior change |
| `test/<name>` | Tests only |
| `chore/<name>` | Tooling, deps, CI, release prep |

Example: `feat/redeem-v01`, `fix/recovery-status-timeout`, `docs/markets-quickstart`.

### 2. Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: implement RedeemClient.auto_redeem_all
fix: handle 1-2s lag in get_trades after fill
docs: add example for take-profit with PnL target
chore: bump py-clob-client-v2 to 1.1.0
```

Single-line subject preferred. Add a body separated by a blank line for the *why* when non-obvious.

### 3. Open a PR

```bash
git push -u origin feat/<name>
gh pr create --fill
```

CI runs:

- `ruff check .` and `ruff format --check .`
- `mypy --strict src/`
- `pytest` on Python 3.10, 3.11, and 3.12

All four must pass before the PR can merge.

### 4. Merge

PRs are **squash-merged**: the PR title becomes the commit subject on `main`, and the PR body becomes the commit body. The feature branch is auto-deleted on merge.

For solo work you can self-merge once CI is green:

```bash
gh pr merge --squash --auto
```

`--auto` waits for CI and merges as soon as the checks pass.

## Local development

```bash
git clone https://github.com/eduardodoege/polymarket-execution.git
cd polymarket-execution
pip install -e ".[dev]"

# Run the same checks CI runs
ruff check .
ruff format --check .
mypy src/
pytest
```

`pyproject.toml` sets `pythonpath = ["src"]` for pytest so tests work without installing the package, but `pip install -e .` is needed for `mypy` and the CLI entry point.

## Scope

**In scope:** execution primitives that wrap raw Polymarket CLOB v2 calls — stop-loss, take-profit, redeem, position sync, order lifecycle, market discovery, recovery layers.

**Out of scope:** trading strategy (when to enter, what to bet, how much). This library is a strategy-agnostic execution layer.

## Releasing

See [RELEASING.md](./RELEASING.md). Maintainer-only.
