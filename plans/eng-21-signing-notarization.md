# ENG-21 — Signed, notarized macOS desktop build (ADR + design)

**Status:** proposed 2026-09-13 · **Tracker:** [#122](https://github.com/lacclab/scanpath-studio/issues/122)

## Context

ENG-15 shipped the standalone desktop bundles, and deliberately deferred code
signing ([`plans/eng-15-desktop-app.md`](eng-15-desktop-app.md) → *Follow-ups*).
The cost of that deferral falls entirely on the audience the desktop build
exists for — reading researchers without a Python toolchain — and it has grown
since v0.25.0:

- **macOS 15 Sequoia removed the Control-click → Open bypass.** The instruction
  at `docs/desktop.md:35` has therefore been wrong for two years. What a user
  actually faces today is System Settings → Privacy & Security → *Open Anyway* →
  confirm → authenticate as an admin, with a one-hour approval window.
- **That affordance is unreliable here anyway.** *Open Anyway* is dependable for
  `.app` bundles and frequently absent for bare Unix executables — which is
  precisely what we ship, and precisely why the docs already need a Terminal
  `xattr -dr com.apple.quarantine` fallback as step 3. A tool distributed to
  avoid the terminal currently requires the terminal to start.
- **Homebrew stopped being an escape hatch.** `--no-quarantine` is deprecated,
  and since 2026-09-01 casks that fail Gatekeeper checks are disabled in the
  official tap. A cask now *requires* notarization rather than avoiding it (and
  the repo misses homebrew-cask's notability threshold by ~28×).

The current `dist/ScanpathStudio/` is a plain folder holding a bare Unix
executable. **That shape can be neither notarized nor stapled** — `notarytool`
accepts only `.zip` / `.dmg` / `.pkg`, and `stapler` attaches tickets only to
`.dmg`, `.pkg` and code-signed *bundles*. So this is not "add a signing step";
the artifact itself has to change.

The existing ad-hoc signature is also weaker than
[`desktop/README.md`](../desktop/README.md) claims: CI signs one Mach-O
(`desktop.yml:50`), so the ~500 MB of `.so`/`.dylib` files under `_internal/`
are unsigned, and `--deep` on a bare executable is a no-op.

## Decision

**Ship a Developer ID–signed, notarized, stapled `.app` inside a signed,
notarized, stapled `.dmg`.** macOS only; Linux and Windows are untouched.

1. **A real bundle.** A darwin-only `BUNDLE()` in the spec produces
   `dist/ScanpathStudio.app`. Gatekeeper blocks double-clicked bare executables
   outright, so the `.app` is what makes "download and double-click" possible at
   all — the signature only removes the warning.
2. **PyInstaller does the signing, and CI verifies it.** `codesign_identity=` /
   `entitlements_file=` on `EXE()` makes PyInstaller sign every collected binary
   inside-out; `BUNDLE` inherits both from the `EXE` it finds and signs the
   bundle itself. This matters for *ordering*: PyInstaller rewrites Mach-O load
   paths, which invalidates any signature applied beforehand, so signing has to
   happen after the bundle is written — which is exactly when PyInstaller does
   it.

   Reading `PyInstaller/utils/osx.py:sign_binary` settles what is left to do:
   its `codesign` call already passes `--timestamp`, `--options=runtime` and
   `--entitlements`, which is the whole of what the notary service checks for.
   So there is **no manual `find … -exec codesign` pass** — the usual
   belt-and-braces loop would add nothing, and the `|| true` it needs (because
   `codesign` fails on the non-Mach-O files the loop also matches) would hide
   real failures. Instead CI *asserts* the three properties on the built bundle
   — hardened-runtime flag, `Developer ID Application` authority, a real
   `Timestamp=` — before spending a notarization submission to discover one is
   missing.

   A happy side effect: with no identity, PyInstaller ad-hoc signs the whole
   bundle deeply. That is already stronger than the pre-ENG-21 CI step, which
   signed one Mach-O and left ~1700 nested binaries unsigned, so the *unsigned*
   fallback needs no extra step either — verified with
   `codesign --verify --deep --strict`, which now passes on the whole bundle.
3. **One entitlement.** `com.apple.security.cs.allow-jit`, and nothing else —
   see *Entitlements* below. The hardened runtime itself is mandatory.
4. **`.dmg` with a drag-to-Applications symlink**, replacing
   `ScanpathStudio-macos-arm64.tar.gz`. Both the `.app` and the `.dmg` are
   notarized and stapled: a stapled `.app` inside an un-notarized `.dmg` does
   launch, but the disk image is itself quarantined on download and Apple's DTS
   advises against shipping the container unsigned.
5. **Quit is "close the tab".** See *A windowless app* below.
6. **Unsigned builds still work.** Every signing step is gated on a secret being
   present, so a fork or a local build degrades to today's ad-hoc behaviour
   rather than failing.

### Credentials

A Developer ID Application certificate requires a **paid Apple Developer Program
membership ($99/yr)**. There is no free path: a free Apple ID gets a Personal
Team limited to development certificates, and Apple's notarization documentation
explicitly names "ad hoc, Apple Developer, or local development" certificates as
invalid. Notarization itself is free with the membership (soft limit: 75
submissions/day).

**Worth one email before paying:** Apple waives the fee for accredited
educational institutions, and Israel is an eligible region, so Technion
plausibly qualifies. The waiver requires *Organization* enrolment (D-U-N-S
number, university legal sign-off, 2–4 weeks) against Individual's ~24–48 hours,
and it is not documented whether a fee-waived membership includes Developer ID
certificates for distribution outside the App Store. The pipeline is
credential-agnostic — it reads repo secrets — so this decision can change later
without reworking anything. **Decision (2026-09-13):** proceed with an
Individual membership now; the waiver can be pursued in parallel.

Seven secrets, all optional (no separate team id — the API key identifies the
team, and the identity string carries it):

| Secret | Value |
|---|---|
| `APPLE_CERT_P12_BASE64` | base64 of the exported Developer ID Application `.p12` |
| `APPLE_CERT_PASSWORD` | the `.p12` export password |
| `APPLE_SIGNING_IDENTITY` | `Developer ID Application: Name (TEAMID)` |
| `KEYCHAIN_PASSWORD` | any strong random string, generated once for CI |
| `APPLE_API_KEY_P8_BASE64` | base64 of `AuthKey_XXXXXXXXXX.p8` |
| `APPLE_API_KEY_ID` / `APPLE_API_ISSUER_ID` | the key's ID and issuer UUID |

An App Store Connect API key rather than an Apple ID + app-specific password:
it is independently revocable and no account password enters the runner. It must
be a **Team** key — Apple's docs state Individual keys "aren't able to use …
`notaryTool`". A solo Individual member is their own Account Holder and can
create one.

## Entitlements

The hardened runtime (`--options runtime`) is mandatory for notarization. The
entitlements usually pasted into Python-bundle guides are not, and were tested
rather than assumed (arm64, macOS 26.6):

- **`allow-unsigned-executable-memory` — omitted.** Plain
  `mmap(PROT_WRITE|PROT_EXEC)` without `MAP_JIT` fails with `EPERM` on Apple
  Silicon under *all* conditions, including with the entitlement granted. It
  does something only on x86_64. The PyInstaller `ctypes` `MemoryError` it is
  cargo-culted from ([#4629](https://github.com/pyinstaller/pyinstaller/issues/4629))
  was an Intel-era bug in old libffi.
- **`disable-library-validation` — omitted.** It is a crutch for incomplete
  signing. The wall it papers over is dyld's *"mapping process and mapped file
  (non-platform) have different Team IDs"* — library validation rejecting nested
  binaries that don't carry our Team ID. Signing all of them (decision 2) is the
  actual fix. Kaleido's downloaded Chrome is a separate *process*, not a loaded
  library, so library validation does not apply to it.
- **`com.apple.security.network.*` — omitted.** These are App Sandbox keys; a
  non-sandboxed Developer ID app ignores them. The Application Firewall is
  separate and does not prompt for loopback listeners.
- **`allow-jit` — kept**, as cheap insurance against a libffi built without
  static trampolines. libffi ≥ 3.4.2 uses them and needs no JIT entitlement at
  all (verified: `CFUNCTYPE(c_int)(lambda: 42)` under hardened runtime with zero
  JIT entitlements, against libffi 3.5.2, plus numpy / scipy / pandas / pyarrow /
  plotly).

If a notarization log or a runtime crash proves one of the omitted keys is
needed, add it with the log line as justification — not pre-emptively.

## A windowless app

`console=True` is actively harmful inside a `.app`, not merely useless. On macOS
it does two things: picks the bootloader, and sets `LSBackgroundOnly` in the
Info.plist. Tested empirically on macOS 26.6.2 with two hand-built bundles:

| | `console=True` (`LSBackgroundOnly`) | `console=False` |
|---|---|---|
| Terminal window on launch | **no** | no |
| inherited fd 0/1/2 | `/dev/null` | `/dev/null` |
| Dock icon / Cmd-Tab | **no** | yes |
| `lsappinfo` type | `BackgroundOnly` | `Foreground` |

No Terminal window appears in either mode, and Launch Services wires
`stdout`/`stderr` to `/dev/null` — the output is *dropped*, not redirected to the
unified log. So `console=True` loses the console **and** hides the Dock icon,
making a double-click look like nothing happened. macOS therefore builds with
`console=False`; Linux and Windows keep `console=True`. This also makes
`docs/desktop.md:5-8` ("the console window that stays open *is* the server")
false on macOS. Two consequences, both handled in `desktop/launcher.py` and
nowhere else:

- **Logs.** An fd-level redirect (`os.dup2` over fds 1 and 2, not just
  rebinding `sys.stdout`) to `~/Library/Logs/Scanpath Studio/`, so C-level
  writes and Kaleido's Chrome subprocess land there too. It must be the first
  statement of `main()`, because Streamlit and Tornado bind logging handlers to
  `sys.stderr` at import time. Gated on "no tty" so a terminal launch is
  unchanged, and wrapped so a read-only home never blocks the launch.
  Console.app reads that directory for free.
- **Quitting.** An app with no Cocoa run loop cannot answer Cmd-Q or Dock → Quit
  — those are Apple Events needing a handler — so the user would get "not
  responding" and Force Quit. Instead a daemon thread polls Streamlit's active
  sessions and calls `os._exit(0)` after a grace period with zero sessions,
  having seen at least one. **Closing the browser tab becomes the quit
  gesture.** No pyobjc, no Cocoa, no change to the Streamlit app, and it works
  because `cli.launch_app` runs the server *in-process*
  (`scanpath_studio/cli.py:138`) — one PID, so no orphan risk.

**The grace is 150 s, and the number is Streamlit's.** A disconnected session
stays restorable in `MemorySessionStorage` for `ttl_seconds = 2 * 60`, so any
grace under two minutes can tear down a session the framework would still have
handed back — a browser that drops the socket and reconnects, a discarded
background tab. Quitting late costs a lingering Dock icon; quitting early costs
unsaved work, so the asymmetry decides it. Laptop sleep is explicitly *not* a
reason: `time.monotonic()` does not advance while a Mac is asleep, so the grace
cannot elapse across a closed lid. `SCANPATH_DESKTOP_IDLE_EXIT_S` overrides it,
and `0` disables it.

Rejected for now: `LSUIElement` (hides the Dock icon, so there is no dead Cmd-Q
— but also no sign the app is running); a pyobjc/Cocoa loop or a Tauri shell
(the ADR's deferred *native window* item, not a packaging change); an in-app
Quit button (app UI, which drags in the four-surface rule and is meaningless on
the hosted and pip surfaces).

## Gotchas addressed

- **The smoke test would go green on the wrong artifact.** PyInstaller's onedir
  `COLLECT` still writes `dist/ScanpathStudio/` *alongside* the `.app` it builds
  from it, so `smoke_test._default_binary()` keeps resolving, `binary.exists()`
  keeps passing, and CI would verify and boot the non-`.app` copy while shipping
  the `.app`. `_default_binary()` becomes darwin-aware and the consumers split:
  the signature check takes the **bundle**, selfcheck and boot take
  `Contents/MacOS/ScanpathStudio`.
- **The release upload glob silently drops a `.dmg`.** `desktop.yml:105` loops
  over `ScanpathStudio-*.tar.gz ScanpathStudio-*.zip`; a `.dmg` matches neither,
  and `if-no-files-found: error` guards the artifact upload, not the release
  loop.
- **`ditto`, not `zip` or `tar`.** `zip` drops the symlinks and extended
  attributes inside a bundle and the notary service rejects it with "The
  signature of the binary is invalid"; `tar` on macOS litters `._` AppleDouble
  files. (`ditto` emits Zip64 above 4 GiB, which Apple's preflight rejects — not
  a risk at ~500 MB, but the reason the `.dmg` is the primary artifact.)
- **Staple the original, not the submission.** Order is sign → `ditto` zip →
  `notarytool submit --wait` → staple the **`.app` on disk** (the zip is
  throwaway and can never hold a ticket) → build the `.dmg` from the stapled
  `.app` → sign, notarize and staple the `.dmg`.
- **`--deep` is fatal here.** The existing
  `codesign --force --deep --sign - --timestamp=none` step is deleted, not
  amended: ad-hoc identity, `--deep` and `--timestamp=none` are each individually
  disqualifying for notarization. `--deep` survives only in the *unsigned
  fallback* path, where ad-hoc signing a bundle is still the pragmatic choice.
- **`notarytool submit --wait`'s exit code is not trustworthy** — a transient
  CFNetwork timeout during status polling exits non-zero while Apple is still
  processing. The submission is wrapped in a script that parses the JSON status
  and prints `notarytool log` on anything but `Accepted`.
- **`CFBundleShortVersionString` takes at most three period-separated
  integers.** `0.30.1` is fine; a PEP 440 pre-release like `0.31.0rc1` is not and
  Apple's validation can reject it, so the spec regexes the version and falls
  back to its numeric prefix rather than discovering this during a tag build.
- **`BUNDLE` takes the `COLLECT`, not the `EXE`** — onedir + `BUNDLE` is the only
  supported combination (onefile + `BUNDLE` already logs a deprecation and
  becomes an error in PyInstaller 7.0). And `BUNDLE` will not accept the `icon`
  **list** the spec builds at line 41: it calls `os.path.isabs(self.icon)`
  directly and raises `TypeError` on a list, so it gets the bare string. The
  bundle identifier is `io.github.lacclab.scanpath-studio` — `codesign` requires
  one, and PyInstaller's default is the bare app name, which is neither unique
  nor reverse-DNS. `version=` must be a `str`; a non-string crashes the bundle at
  launch.
- **`LSMinimumSystemVersion` has to be honest, and the floor is the wheels'.**
  scipy and numpy ship arm64 binaries built with `minos 14.0` — 98 of them in a
  current build — so the `12.0` this key was first given would have let the app
  launch on macOS 12 and die in dyld, which is the failure the key exists to
  prevent. It is `14.0`. orjson is built for 15.0 but does not raise the floor:
  plotly imports it in a `try/except` and falls back. Re-check with `otool -l`
  after any scipy/numpy bump.
- **`security find-identity` exits 0 even when it finds nothing**, printing
  "0 valid identities found" — so the import step's fail-fast guard greps the
  output rather than trusting the exit code, which would otherwise let a bad
  certificate reach `codesign` three steps later.
- **All seven secrets or none.** A partial set is a setup mistake, not a
  deliberate unsigned build, and testing only the certificate would let it reach
  `notarytool` and fail there with an auth error that names nothing. The gate
  fails loudly and lists what is missing.
- **Keychain handling.** `set-key-partition-list` is required or `codesign` dies
  with `errSecInternalComponent`; `set-keychain-settings -lut` is required or the
  keychain auto-locks after 300 s mid-build; and the new keychain is *prepended*
  to the search list (`-s <one>` replaces it and would drop the login keychain
  for the rest of the job).

## Verification

**Two risks are retired by building locally before any CI work**, because both
would invalidate the packaging half regardless of signing:

1. **Does `importlib.resources.files("scanpath_studio").joinpath("app.py")`
   resolve inside the bundle?** `cli.launch_app:127` needs the packaged `app.py`
   as a real file path, and inside a `.app` the sources live under
   `Contents/Resources` reached by cross-link from `Contents/Frameworks`. The
   mechanism says yes; it has never been built and run. This is the single
   highest-value first test.
2. **Does Kaleido find a Chrome from inside the `.app`?** Launch Services gives
   the process a bare `PATH`, so PNG/SVG/PDF export could be the one broken
   surface — HTML export is browser-free either way.

`desktop/smoke_test.py` gains a macOS gate, expressed so unsigned builds still
pass: `codesign --verify --strict` always, and — only when
`SCANPATH_EXPECT_NOTARIZED=1` — `stapler validate` plus
`spctl -a -vvv -t exec` expecting `source=Notarized Developer ID`.

`stapler validate` is the load-bearing check: it proves a ticket is *physically
attached*, which is what makes an offline first launch work. `spctl` on the
build machine is weaker than it looks — the artifact has no quarantine xattr
there and the local ticket database may already hold the ticket.

The only unimpeachable test is manual and belongs on the release checklist:
download the released `.dmg` on a machine that has never seen it, confirm
`xattr -p com.apple.quarantine` is present, and open it.

## Alternatives considered

- **Wrap the existing folder in a `.dmg` or `.pkg`** without making it a `.app` —
  rejected: it notarizes, but the user still gets a folder and a console binary
  they must launch from Terminal, which is the whole problem.
- **`.zip` of the `.app` instead of a `.dmg`** — viable and simpler (one
  notarization), but a `.zip` can never be stapled and there is no install
  gesture, so the app lives in Downloads forever.
- **Mac App Store** — removes the friction, but adds App Review and the App
  Sandbox, which a PyInstaller/Streamlit app with a bundled Chrome would not
  survive.
- **Homebrew cask / self-signed `.pkg` / pip** — none remove the terminal; see
  *Context*. `pip install scanpath-studio` remains genuinely frictionless for
  Python users (pip-installed code is never quarantined) and stays the primary
  channel for them.

## Follow-ups (out of scope)

- **Windows Authenticode — ENG-47.** Split from this item deliberately: per
  Microsoft's own documentation, EV certificates stopped bypassing SmartScreen
  in 2024, so signing no longer buys a clean first run and the cost/benefit is a
  separate decision.
- **Intel macOS** (a `macos-13` leg) — unchanged from ENG-15; still
  Apple-silicon only.
- **`icon.icns` is written by Pillow**, which emits a narrower size set than
  `iconutil`. Tolerable for an embedded exe icon, marginal for a Dock/Finder
  `.app` icon.
- **A native window** (pywebview / Tauri) — still the ENG-15 follow-up it was.
