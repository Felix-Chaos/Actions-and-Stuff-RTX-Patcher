# Security Policy

The Actions & Stuff RTX Patcher is a native desktop app (Tauri + Rust) that reads and writes
files under your Minecraft installation, downloads patch payloads from the network, and shells
out to a couple of external tools. That's a real attack surface, so this document explains what's
in scope, how to report a problem privately, and what we've already done about it.

## Supported Versions

Only the latest released version is supported. The in-app updater checks
[`updater.json`](updater.json) on every launch and installs signed updates automatically, so
staying current is a one-click action, not a maintenance burden.

| Version         | Supported          |
| --------------- | ------------------- |
| Latest release  | :white_check_mark:   |
| Anything older  | :x:                  |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

The preferred channel is **[GitHub Private Vulnerability Reporting](https://github.com/Felix-Chaos/Actions-and-Stuff-RTX-Patcher/security/advisories/new)**
(Security tab → Report a vulnerability). It creates a private advisory that only maintainers can
see until it's resolved, and lets us coordinate a fix and a disclosure date with you directly.

If you'd rather not use GitHub, DM **@felixchaos** on Discord (the
[ChaosDev Projects](https://discord.gg/YrMMmN2kc7) server), or open a private thread there. Please
don't post details in a public channel first.

When reporting, include what you'd include in any good bug report, plus the security-specific
bits:

- What you found and why it's exploitable (a PoC or repro steps help a lot).
- The affected version (`Actions & Stuff RTX Patcher.exe`'s version, visible in App Settings).
- Impact: what an attacker could actually do with it (arbitrary file write, code execution,
  credential exposure, etc.).

**Response time:** we aim to acknowledge within 72 hours and give you an initial assessment
within a week. This is a community project maintained outside working hours, so please be
patient — but we do take reports seriously and will keep you updated.

If the report is valid, we'll credit you in the fix's release notes (unless you'd rather stay
anonymous) once a patch has shipped.

## Scope

**In scope:**

- The patcher application itself (`src-tauri/`, `src/`) — this repository.
- The [patch library repo](https://github.com/Felix-Chaos/AS-RTX-Patch-Library) and its CI, since
  the patcher trusts and downloads from it automatically.
- The [GitHub Pages site](https://felix-chaos.github.io/Actions-and-Stuff-RTX-Patcher/) (`gh-pages`
  branch), for things like XSS in the site itself.
- The GitHub Actions workflows under `.github/workflows/`, since a compromised workflow could
  publish a malicious release.

**Out of scope:**

- Minecraft Bedrock, the Marketplace, or Mojang/Microsoft's own systems.
- BetterRTX itself — report through [bedrock.graphics](https://bedrock.graphics/) or its
  [Discord](https://discord.gg/HPP6J4qFPu), not here.
- The original *Actions & Stuff* pack content — this project only ships binary diffs
  (`.vcdiff`) against a copy you already own; it never redistributes the original assets. Content
  or licensing concerns about the pack itself belong with its original creator, not here.
- Social engineering, physical access, or issues that require the attacker to already have
  arbitrary code execution on your machine.

## What's already in place

A rough log of what's been hardened, so reporters can build on it rather than rediscover it:

- **Locked-down webview CSP.** The webview used to run with `security.csp: null` and unrestricted
  `invoke()` access; it now runs under a restrictive `default-src 'self'` policy
  (`src-tauri/tauri.conf.json`), so a script injected via any future XSS bug can't freely call
  privileged Tauri commands like deleting files.
- **Signed auto-updates.** Updates are verified against an embedded minisign public key
  (`tauri.conf.json`'s `updater.pubkey`) before being applied — a compromised or MITM'd
  `updater.json` can't push an unsigned build.
- **Path traversal fixes.** `.brarchive` entry names and extracted zip/mcpack paths are validated
  before writing, so a crafted archive can't escape the target directory.
- **Restricted `open_url`.** Only `http(s)` URLs are ever passed to the OS's URL handler, and never
  through a shell that could re-parse `&`/`|` as command separators.
- **Privacy-first telemetry.** Hardware pings are opt-in, identified only by a random install ID
  and a one-way SHA-256 hash of the machine GUID (the GUID itself never leaves the machine), and
  deletable at any time from Settings ("Delete My Data").
- **Dependency updates.** `dependabot.yml` covers `npm`, `cargo`, and `github-actions` ecosystems.

None of this means the app is bulletproof — if you find a gap in any of the above, that's exactly
what this policy is for.
