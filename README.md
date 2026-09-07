# blackbox

[![CI](https://github.com/BabaMboga/blackbox-void/actions/workflows/ci.yml/badge.svg)](https://github.com/BabaMboga/blackbox-void/actions/workflows/ci.yml)

**Encrypt it. Disguise it. Hide it. Dare them to find it.**

blackbox is a cross-platform, open-source command-line vault. Point it at a
folder — by default, one named **The Void** — and it seals the contents
behind real, industry-standard encryption, renames the sealed file to
something boring, and hides it from a casual glance. It also has opinions
about trivia, occasionally leaves you a message in runes, and is not,
strictly speaking, sorry about any of that.

<!-- TODO: replace with a real terminal-recording GIF before v1.0.0 ships.
     Suggested tool: https://github.com/charmbracelet/vhs or asciinema+agg.
     Show: blackbox init -> lock -> status -> unlock, including the
     Matrix-rain animation and one trivia/fake-message line. -->
![blackbox demo](docs/demo.gif)

---

## What it actually does

| Layer | Real protection or deterrent? | How |
| --- | --- | --- |
| **Encryption** | Real. This is the only actual security boundary. | AES-256-GCM, key derived via Argon2id (OWASP-recommended, memory-hard) |
| **Disguising** | Deterrent only. | Renames the sealed file to something boring (`ntuser.dat.tmp`, `swapfile.sys`, etc.) |
| **Hiding** | Deterrent only. | OS-native hidden attributes (Windows) or dotfile convention (macOS/Linux) |
| **Cooldown on wrong password** | Friction only. | Doubles each failed attempt (1s, 2s, 4s...), capped — never locks you out permanently |

**Read that table again if you're evaluating this for anything serious.**
Disguising and hiding will stop a casual glance. They will not stop a
determined attacker, a forensic tool, or anyone who knows to toggle "show
hidden files." The encryption is what actually protects your data. We say
this plainly because oversold security is worse than none.

Passwords are never stored, anywhere, in any form. Only a random salt is
kept, alongside the sealed vault.

## Installation

### From a release (recommended — no Python required)

Download the binary for your OS from the
[**Releases**](https://github.com/BabaMboga/blackbox-void/releases) page:

| OS | File |
| --- | --- |
| Windows | `blackbox-windows.exe` |
| macOS | `blackbox-macos` |
| Linux | `blackbox-linux` |

On macOS/Linux, make it executable and optionally move it onto your `PATH`:

```bash
chmod +x blackbox-macos   # or blackbox-linux
sudo mv blackbox-macos /usr/local/bin/blackbox
```

On Windows, just double-click `blackbox-windows.exe` — it opens a real
console window and walks you through it. (macOS/Windows binaries are
currently unsigned, so your OS will show a first-run security warning;
click through it — "More info -> Run anyway" on Windows,
"right-click -> Open" on macOS.)

### From source (requires Python 3.9+)

```bash
git clone https://github.com/BabaMboga/blackbox-void.git
cd blackbox-void
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\Activate.ps1
pip install -e .
blackbox status
```

## Usage

```bash
# First run: creates "The Void" folder for you
blackbox init

# Drop whatever you want to disappear into The Void, then:
blackbox lock

# Check on it later
blackbox status

# Bring it back
blackbox unlock
```

That's the whole interface. Four commands.

```text
Usage: blackbox [OPTIONS] COMMAND [ARGS]...

  blackbox — hide it. lock it. dare them to find it.

Commands:
  init     Create The Void, if it doesn't already exist.
  status   Show whether a vault is currently locked or unlocked.
  lock     Encrypt FOLDER into a sealed, disguised, hidden vault.
  unlock   Decrypt FOLDER's vault back into FOLDER.
```

Both `lock` and `unlock` accept a folder name if you don't want to use the
default:

```bash
blackbox lock "My Other Secrets"
blackbox unlock "My Other Secrets"
```

And both accept `--fast` if you'd rather skip the loading animation:

```bash
blackbox lock --fast
```

### A note on passwords

`lock` asks for your password twice (a typo here could lock you out of your
own data). `unlock` asks once. Neither ever echoes what you type, and
neither is ever written to disk in any form — only a random salt is kept,
which is not sensitive on its own.

If you get the password wrong, blackbox makes you wait a little longer
before the *next* attempt, and a little longer than that on the one after —
this is pure friction against rapid guessing, not a real security
mechanism, and it will never lock you out of a correct password.

## How The Void works

The Void has exactly two states, and it's always exactly one of them:

- **Unlocked** — `The Void/` exists as a plain folder you can open and edit.
- **Locked** — the folder is gone; in its place is a single encrypted file,
  renamed to something forgettable and hidden from a plain directory
  listing.

`blackbox status` will tell you which state you're in without ever
revealing what the locked file is actually disguised as — printing that
would defeat the point.

## Project structure

```text
blackbox-void/
  src/blackbox/
    crypto.py        Password -> key derivation (Argon2id)
    vault.py          lock() / unlock() — archive, encrypt, decrypt
    hide.py           OS-level hiding (hide_path / unhide_path)
    config.py          The Void's lifecycle + disguise naming
    ui.py             Matrix-rain loading animation
    easter_eggs.py    Trivia, fake messages, a rune substitution table
    cli.py            The actual `blackbox` command
  tests/              One test file per module, ~180 tests total
  installer/          Per-OS PyInstaller build scripts
  .github/workflows/  CI (every push/PR) + release builds (tagged pushes)
```

## Testing

```bash
pip install -e ".[dev]"
pytest
```

Runs the full suite — encryption correctness, lock/unlock round trips,
OS-specific hiding behavior (auto-skipped on non-matching platforms),
CLI end-to-end flows via Click's test runner, and path-handling edge cases
(unicode, spaces, deeply nested folders).

## Contributing

Contributions are welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md) for
the dev setup, commit conventions, and what a good PR looks like around
here. There's also a running list of trivia facts and fake ominous system
messages in `easter_eggs.py` that could always use more entries, if that's
more your speed than encryption internals.

## Security disclosure

If you find a genuine security issue (not "the disguise name is
guessable" — we know, that's the deal), please open an issue marked
`security` or reach out to the maintainer directly rather than filing a
public issue with exploit details.

## License

MIT — see [`LICENSE`](LICENSE).

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

---

*Did you know: the concept of a mathematical "void" (the empty set) was
formalised by Ernst Zermelo in 1908 — meaning the idea of "nothing" is,
itself, younger than the light bulb. blackbox has opinions like this. You
will see more of them.*
