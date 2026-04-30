# Releasing

This project publishes to PyPI from GitHub Actions via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC, no API tokens).

## One-time setup

These steps are done once per project — already configured for this repo:

1. **PyPI account** with 2FA — https://pypi.org/account/register/
2. **PyPI trusted publisher** — https://pypi.org/manage/account/publishing/
   - Project name: `polymarket-execution`
   - Owner: `eduardodoege`
   - Repository name: `polymarket-execution`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
3. **GitHub environment** `pypi` in this repo — *Settings → Environments → New environment → "pypi"*
   - Recommended: enable **Required reviewers** so each publish requires a manual click in the Actions tab.

## Cutting a new release

1. Bump the version in `src/polymarket_execution/_version.py`
2. Update README / docs if any user-facing API changed
3. Commit:
   ```bash
   git commit -am "Release v0.1.0"
   ```
4. Create and push the tag (must match the version exactly, prefixed with `v`):
   ```bash
   git tag v0.1.0
   git push origin main
   git push origin v0.1.0
   ```
5. The `publish.yml` workflow:
   - Verifies that the tag matches `pyproject.toml` version (fails otherwise)
   - Builds the sdist + wheel
   - Publishes to PyPI via OIDC
6. If you enabled "Required reviewers" on the `pypi` environment, approve the run in the **Actions** tab
7. Within ~2 minutes, `pip install polymarket-execution==0.1.0` works for the world

## Pre-release versions

Use PEP 440 suffixes: `0.1.0a1`, `0.1.0b2`, `0.1.0rc1`, `0.1.0.dev0`. The publish workflow handles them transparently — same flow, same tag prefix (`vX.Y.Z<suffix>`).

## Yanking a bad release

If a published version is broken, **don't delete it** (PyPI doesn't allow re-uploading the same version). Instead:

1. Push a new patch version with the fix
2. On PyPI, mark the bad version as "yanked" via the project page (browser only)
