# blackbox — Manual QA Checklist (v2)

Supersedes the first walkthrough. Incorporates three real bugs found during
that first pass — the animation cutting off abruptly, the orphaned-vault
bug, and the missing persistent-password check — plus the fixes for all
three. Run this in full before tagging any release.

**Rule for this pass:** every time you find something that feels off,
stop and write it down immediately, in your own words, before deciding
whether it's a bug or intended behavior. Two of the last three real bugs
were only caught because something *looked* wrong before anyone could
explain *why* it was wrong.

---

## Step 0 — Clean slate

Do not reuse a folder with history in it — leftover registry/identity
files will hide real bugs (this is exactly what happened last time with
the orphaned vault).

```bash
cd ~
rm -rf blackbox-manual-qa   # if it exists from a previous pass
mkdir blackbox-manual-qa && cd blackbox-manual-qa
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\Activate.ps1
git clone https://github.com/BabaMboga/blackbox-void.git
cd blackbox-void
git checkout <your-branch-with-all-the-fixes>
pip install -e ".[dev]"
```

- [ ] `pytest -v` fully green before doing anything manual

---

## Step 1 — `blackbox init`

```bash
cd ~/blackbox-manual-qa
blackbox init
```

- [ ] Prints `Ready: <path>/The Void`
- [ ] `The Void/README.txt` exists, reads cleanly, no typos
- [ ] Running `init` again is a no-op — doesn't touch a file you drop inside first
- [ ] `blackbox init --name "MyStuff"` creates a second, independent vault folder

---

## Step 2 — `blackbox status` in every state

- [ ] Nothing created yet → "hasn't been created yet," with the fake
      mainframe delay playing first
- [ ] After `init` → "Unlocked"
- [ ] After `lock` → "Locked. (hidden and disguised)" — **never** prints
      the actual disguised filename anywhere in the output

---

## Step 3 — The animation, specifically checking the fix

```bash
echo "test" > "The Void/note.txt"
blackbox lock
```

- [ ] Watch it run start to finish, unhurried. It should now visibly run
      for a real, deliberate duration — **not** blink and vanish almost
      instantly the way it did on the first QA pass.
- [ ] Confirm it still finishes and returns control to you — it shouldn't
      hang indefinitely either.
- [ ] Now type a **wrong** password on a fresh lock/unlock cycle and
      confirm the error is reported **immediately** — the minimum
      animation duration must never apply to a failure. If a wrong
      password now takes noticeably long to fail, that's a regression.

---

## Step 4 — Persistent password (the new feature)

This is the newest, least-battle-tested part of the app — spend real time
here.

```bash
blackbox unlock --fast          # get back to a clean unlocked state
blackbox lock --fast
# type: cashmoney700t / cashmoney700t
```

- [ ] Locks successfully (first-ever lock for this vault name — nothing
      to compare against yet)

```bash
blackbox unlock --fast
# type: cashmoney700t
```

- [ ] Unlocks correctly

```bash
blackbox lock --fast
# type: cashmoney700t / cashmoney700t   (the SAME password again)
```

- [ ] Succeeds — reusing the same password on a later lock must work
      cleanly, not be treated as suspicious

```bash
blackbox unlock --fast
# type: cashmoney700t
blackbox lock --fast
# type: 1234 / 1234    (a DIFFERENT password this time)
```

- [ ] **This must now be rejected.** Look for:
  "this vault was previously locked with a different password."
- [ ] Exit code is non-zero
- [ ] **Critically:** run `ls` right after the rejection — `The Void`
      must still exist as a plain, untouched folder. It must **not** have
      been encrypted, disguised, or hidden. A rejected password-mismatch
      lock should leave zero trace of having attempted anything.

```bash
blackbox lock --fast --change-password
# type: 1234 / 1234
```

- [ ] This should succeed even though `1234` differs from the previously
      recorded password — `--change-password` is the deliberate override

```bash
blackbox unlock --fast
# type: cashmoney700t     (the OLD password)
```

- [ ] Should now fail — the old password is no longer valid

```bash
blackbox unlock --fast
# type: 1234              (the NEW password)
```

- [ ] Should succeed

- [ ] Delete `.blackbox_vault_identity.json` by hand (`rm .blackbox_vault_identity.json`)
      after locking once, then try locking again with a different
      password. Confirm it's treated as a fresh first-lock (accepted, no
      rejection) — fail-open behavior, matching how the disguise registry
      already fails open on a missing/corrupted file.

---

## Step 5 — The orphaned-vault regression (previously a real bug)

```bash
blackbox unlock --fast
blackbox lock --fast
# lock it once, any password
blackbox init
```

- [ ] `init` must return the "currently locked" message — **not** silently
      create a fresh empty `The Void` folder. If a new empty folder
      appears here, the orphaned-vault bug is back.

```bash
ls -la
```

- [ ] Confirm there is exactly **one** hidden disguised vault file, not
      two. (This is the exact symptom from the original bug — a second,
      orphaned disguised file sitting alongside the first.)

---

## Step 6 — Hidden files, properly checked this time

```bash
ls
```

- [ ] Plain `ls` (no flags) shows **nothing** related to the vault —
      not the disguised file, not the registry, not the identity file

```bash
ls -la
```

- [ ] `-a` will correctly show all of them (`.blackbox_disguise_registry.json`,
      `.blackbox_vault_identity.json`, the disguised vault file) — this is
      expected; `-a` means "show hidden files," it isn't a failure of hiding

- [ ] Open `.blackbox_disguise_registry.json` and `.blackbox_vault_identity.json`
      directly. Confirm neither contains a password, a raw encryption key,
      or anything beyond filenames/salts/one-way hashes.

- [ ] **If you're on native Windows** (not WSL): right-click → Properties
      on both files, confirm the "Hidden" attribute checkbox is genuinely
      checked, not just relying on the leading dot in the filename (which
      means nothing to Windows Explorer on its own).

---

## Step 7 — Full unlock cycle, wrong password, repeated

```bash
blackbox lock --fast    # any password, call it PASS
blackbox unlock --fast  # deliberately wrong password
```

- [ ] Fails clearly, non-zero exit
- [ ] `The Void` not restored
- [ ] `status` still says "Locked"
- [ ] Vault still fully hidden (plain `ls` shows nothing)

```bash
blackbox unlock --fast  # wrong again
```

- [ ] Noticeably longer cooldown before failing than the first wrong
      attempt (doubling cooldown)

```bash
blackbox unlock --fast  # PASS, correct this time
```

- [ ] Restores successfully, content intact

Repeat this whole cycle **3–4 more times** — the disguised filename is
random each time, so repetition is how you catch a bug that only shows
up under a specific chosen name (exactly how the earlier `.DS_Store.bak`
dot-collision bug was found).

---

## Step 8 — Easter eggs

- [ ] `blackbox --konami` prints the message, touches nothing on disk
- [ ] `--konami` absent from `blackbox --help`
- [ ] `blackbox` with no arguments shows normal help, not blank output
- [ ] Lock/unlock 10–15 times, actually read each trivia/fake-message
      line — check for typos, check none read as genuinely alarming
      rather than obviously playful

---

## Step 9 — Error paths

- [ ] `blackbox lock DoesNotExist --fast` → clear error
- [ ] `blackbox lock <a-plain-file> --fast` → clear "not a folder" error
- [ ] `blackbox unlock --fast` with nothing ever locked → clear
      "no locked vault found," not a traceback

---

## Step 10 — Unusual but legal inputs

- [ ] Folder name with spaces: `blackbox init --name "My Backup Files"`,
      full lock/unlock cycle
- [ ] Unicode folder name if your terminal supports it easily

---

## Step 11 — The real compiled binary

Source-mode testing (`pip install -e .`) does **not** prove the shipped
binary works — packaging can break things source mode never would.

```bash
python installer/build_linux.py   # match your OS
```

Run a full condensed cycle — `init → lock → wrong password → correct
unlock → lock again same password → lock again different password
(should reject)` — using `./dist/blackbox` directly.

- [ ] Everything from Steps 3, 4, and 5 above holds true against the
      compiled binary too, not just the source install

---

## Step 12 — Cross-platform

Three of the real bugs found so far (`SetFileAttrbutesW` typo, the
`tarfile filter` Python-version issue, and the Windows-specific
`_visible_entries()` gap) were **only** ever caught by CI running on
real macOS/Windows — not by local single-OS testing.

- [ ] Confirm the full CI matrix is green across all OS × Python
      combinations before treating any of the above as verified on
      platforms you can't test by hand
- [ ] If you have access to a second machine, repeat at minimum Steps 3,
      4, and 5 there

---

## Final go/no-go

- [ ] `pytest -v` green locally
- [ ] Full CI matrix green
- [ ] Every command manually walked through, output actually read
- [ ] Persistent password feature: same-password-succeeds,
      different-password-rejected, `--change-password` override, and
      fail-open-on-missing-file all confirmed by hand
- [ ] Orphaned-vault regression confirmed fixed
- [ ] Animation confirmed to run a real duration on success, and to
      never delay a failure
- [ ] Registry/identity files confirmed to contain no cryptographic
      material, and confirmed genuinely hidden (not just dot-prefixed)
- [ ] At least one full cycle run against the compiled binary
- [ ] No password, disguised filename, or vault identity ever printed
      anywhere it shouldn't be

Only once every box above is checked — not just the automated suite —
should this get tagged.
