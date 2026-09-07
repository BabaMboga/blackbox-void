# Contributing to blackbox

Thanks for considering it. This project is small, opinionated, and tries
to have fun without cutting corners on the parts that actually matter
(the encryption). Here's how to get set up and what a good contribution
looks like around here.

## Dev setup

```bash
git clone https://github.com/BabaMboga/blackbox-void.git
cd blackbox-void
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest                        # confirm everything's green before you start
```

`pip install -e ".[dev]"` pulls in the runtime dependencies
(`cryptography`, `click`, `rich`, `argon2-cffi`) plus the dev/build tools
(`pytest`, `pytest-cov`, `pyinstaller`). If you only want to run blackbox
rather than develop it, `pip install -e .` alone is enough.

## Branching

Branch names follow `<type>/<short-description>`, matching the commit
type it'll mostly contain:

```text
feature/vault-failed-attempt-cooldown
fix/undisguise-vault-wrong-variable
test/vault-lock-unlock
docs/readme-install-instructions
```

## Commit messages

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <short, present-tense description>
```

- **type** — `feat`, `fix`, `test`, `docs`, `chore`, `style`, `ci`, `refactor`
- **scope** — the module or area touched: `crypto`, `vault`, `hide`,
  `config`, `ui`, `easter-eggs`, `cli`, `installer`, `ci`, `tests`

Examples pulled straight from this project's real history:

```text
feat(vault): derive 256-bit keys from password using Argon2id
fix(config): use original_name instead of disguised_name in undisguise_vault()
test(hide): add platform-independent and OS-gated coverage for hide_path()
docs(tests): add explanatory docstrings to every test_vault.py function
ci(build): add per-OS build matrix, since PyInstaller cannot cross-compile
```

A few conventions we lean on:

- **Split unrelated changes into separate commits**, even within the same
  file — a typo fix and a real behavior change shouldn't share a commit.
- **`feat` and its tests are usually separate commits** (`feat(...)` then
  `test(...)`), even when written in the same sitting, unless the file was
  genuinely written whole in one pass.
- **`fix` is for correcting something already committed** (even if not
  yet merged), not for first-draft functionality — that's still `feat`.

## Before opening a PR

```bash
pytest -v
```

All tests should pass. If you're touching OS-specific code in `hide.py`,
note that Windows/macOS-specific tests will `SKIP` (not fail) on other
platforms — that's expected; they run for real in CI's per-OS matrix.

## What a good PR looks like here

- **Title**: same format as a commit — `type(scope): description`.
- **Description** covers: what changed, why (especially for any design
  decision that isn't obvious from the diff alone), how it was verified,
  and what's deliberately *not* included (scope boundaries matter more
  than they might seem — a PR that's honest about its limits is easier to
  review and merge than one that quietly overreaches).
- **If your PR fixes a bug found while building or testing something
  else**, say so explicitly, and explain the root cause — not just the
  patch. Several real bugs in this project were only caught because a
  test's *reasoning* was written down, not just its assertion.

## Code style notes

- **Docstrings explain *why*, not just *what***. `# renames to a dotfile`
  is fine as a start; `# renames to a dotfile because Finder doesn't
  reliably hide based on flags alone in every view` is what we're going
  for.
- **Security-relevant code gets extra care.** If you're touching
  `crypto.py` or the encryption path in `vault.py`, explain your reasoning
  in the PR even if the diff is small — this is the one part of the
  codebase where "it works" isn't the same bar as "it's correct."
- **Never claim a security property the code doesn't actually provide.**
  If something is a deterrent, say deterrent. This project is deliberately
  upfront about what's real protection (encryption) versus friction
  (hiding, disguising, cooldowns) — new code should keep that honesty.

## Adding to `easter_eggs.py`

Two content pools live there: `TRIVIA_FACTS` (must be genuinely true —
we've had contributors fact-check entries before merging) and
`FAKE_SYSTEM_MESSAGES` (should read as obviously, self-awarely fake —
campy hacker-movie energy, never a real-sounding threat). If you're
adding to either, keep entries free of duplicates and roughly consistent
in tone with what's already there.

## Questions

Open an issue, or start a discussion if the repo has one enabled. There's
no dumb question here — half of this codebase exists because someone
asked "wait, why does this work that way?" and the answer turned out to
be a real bug.
