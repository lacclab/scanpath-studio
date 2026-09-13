# Setting up macOS signing (ENG-21)

One-time setup so the `Desktop builds` workflow signs and notarizes the macOS
app. Until these secrets exist the workflow still runs and still produces a
`.dmg` — it just logs a warning and ships an unsigned build, which users cannot
open without a trip to System Settings.

Rationale and the technical design are in
[`../plans/eng-21-signing-notarization.md`](../plans/eng-21-signing-notarization.md).

**Nobody but the account holder should do steps 1–4** — they involve an Apple
account password and a private key. Steps 5's commands read files you exported
and never print their contents.

---

## 1. Apple Developer Program membership

Enrol at <https://developer.apple.com/programs/enroll/>. **$99/year**, Individual
enrolment, usually approved within 24–48 hours. There is no free alternative: a
free Apple ID gets a Personal Team that cannot issue a Developer ID certificate,
and Apple's notarization service rejects ad-hoc and development certificates.

!!! tip "Possibly free"
    Apple [waives the fee](https://developer.apple.com/help/account/membership/fee-waivers/)
    for accredited educational institutions, and Israel is an eligible region, so
    Technion plausibly qualifies. The waiver needs **Organization** enrolment
    (D-U-N-S number, university legal sign-off, 2–4 weeks) rather than
    Individual, and it is not documented whether a fee-waived membership includes
    Developer ID certificates for distribution *outside* the App Store — worth
    confirming with Apple before relying on it. Nothing below changes if you
    switch later: the pipeline reads secrets, not a specific account.

## 2. Create a Developer ID Application certificate

Xcode is already the easiest route:

**Xcode → Settings → Accounts →** select your Apple ID **→ Manage Certificates…
→ + → Developer ID Application**.

It lands in your login keychain. Confirm it is there — the whole string is
`APPLE_SIGNING_IDENTITY`, and the 10 characters in the parentheses are your Team
ID (the pipeline reads it back out of the identity, so it is not a separate
secret):

```bash
security find-identity -v -p codesigning
```

You want the line reading `Developer ID Application: Your Name (ABCDE12345)`.

## 3. Export the certificate as a `.p12`

**Keychain Access → My Certificates**, find `Developer ID Application: …`,
**expand the disclosure triangle and select the certificate row** (that is the
one carrying the private key), right-click → **Export** → save as
`DeveloperID.p12` and set a password. That password becomes
`APPLE_CERT_PASSWORD`.

## 4. Create an App Store Connect API key

**App Store Connect → Users and Access → Integrations → App Store Connect API →
Team Keys → +**. Name it something like `notarization-ci`, access role
**Developer**.

!!! warning "It must be a *Team* key"
    Apple's documentation states that Individual keys "aren't able to use
    Provisioning endpoints, access Sales and Finance, or `notaryTool`". An
    Individual key fails at the notarization step with a confusing auth error. As
    a solo Individual member you are your own Account Holder, so you can create a
    Team key — just make sure you are on the **Team Keys** tab.

Download the `AuthKey_XXXXXXXXXX.p8` — **Apple lets you download it once**. Note
the **Key ID** (10 characters) and the **Issuer ID** (a UUID, shown above the
table).

## 5. Add the repository secrets

Seven secrets. Run this from the repo, with the two files you just downloaded;
it reads them and hands them straight to GitHub without printing them:

```bash
base64 -i ~/Downloads/DeveloperID.p12 | gh secret set APPLE_CERT_P12_BASE64 -R lacclab/scanpath-studio
```

```bash
base64 -i ~/Downloads/AuthKey_XXXXXXXXXX.p8 | gh secret set APPLE_API_KEY_P8_BASE64 -R lacclab/scanpath-studio
```

Then the four short ones — `gh` prompts for each value, so nothing lands in your
shell history:

```bash
for s in APPLE_CERT_PASSWORD APPLE_SIGNING_IDENTITY APPLE_API_KEY_ID APPLE_API_ISSUER_ID; do
  printf '\n%s: ' "$s"; read -rs value; echo
  printf '%s' "$value" | gh secret set "$s" -R lacclab/scanpath-studio
done
```

Finally a keychain password, which is just a random string CI uses to unlock the
temporary keychain it creates:

```bash
openssl rand -base64 24 | tr -d '\n' | gh secret set KEYCHAIN_PASSWORD -R lacclab/scanpath-studio
```

Check all seven are present:

```bash
gh secret list -R lacclab/scanpath-studio
```

## 6. Verify before you rely on it

Trigger the workflow by hand rather than discovering a problem during a release:

```bash
gh workflow run desktop.yml -R lacclab/scanpath-studio && sleep 5 && gh run list --workflow=desktop.yml -R lacclab/scanpath-studio --limit 1
```

On the macOS leg, confirm the log shows `Notarization accepted` and that the
`Re-verify the stapled bundle` step passed. A *partial* set of secrets fails the
job loudly, but **all seven missing only logs a warning** and still ships an
unsigned bundle — so a green run is not by itself proof the build was signed.

Then the only test that really counts: download the `.dmg` from the run's
artifacts onto a Mac that has never seen it, confirm it is quarantined, and open
it.

```bash
xattr -p com.apple.quarantine ~/Downloads/ScanpathStudio-macos-arm64.dmg
```

## Maintenance

- **The certificate expires after 5 years**; the membership lapses annually if
  not renewed. An expired membership does not break already-notarized builds —
  stapled tickets stay valid — but no new build can be signed.
- **The `.p8` key** can be revoked and reissued from App Store Connect at any
  time if it leaks. Rotate by repeating step 4 and re-running the two
  `gh secret set` commands.
- **Never commit** the `.p12`, the `.p8`, or their passwords. Delete the
  downloads once the secrets are set.
