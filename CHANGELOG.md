# Changelog

Changes to fxxk u tibo are recorded here. Release entries describe behavior; they are not test reports.

## v0.1.1 — project rename and multilingual slogan

- Rename the project to **fxxk u tibo** and the repository to **LocusQiang/fxxk-u-tibo**. The previous name was Codex Auto Retry Kitchen.
- Put the original slogan on both README pages and add [60 language versions](docs/slogan-translations.md). These are documentation translations; the application UI remains English and Chinese.
- Update repository links, launcher display titles, and source archive naming. The source allowlist now contains 79 files, including the new translation page.
- Keep retry behavior, saved runtime state, scheduled-task identity, mutex names, and the desktop protocol client identifier unchanged for compatibility. Existing v0.1.0 release artifacts retain their original names.

## v0.1.0 — initial public release

Completed checks, tested revisions, and remaining validation gaps are recorded in [Compatibility](docs/compatibility.md#release-validation-record).

### Added

- Windows desktop companion targeting Windows 10/11 x64, using Python 3.11–3.14 with tkinter, Node.js 22+, and Pillow 12.2.0.
- Automatic continuation of new, verified service-unavailable, HTTP 503, overload, and capacity failures with the literal Chinese message `继续`, inheriting the original conversation's settings and approval boundaries.
- A persistent baseline at first normal Start that skips pre-existing failures; archived and subagent conversations are excluded. Archived conversations cannot be enabled in this public version.
- Persistent send records, at least 30 seconds between sends to the same chat, and no automatic resubmission after an unknown outcome.
- Submission checks for the exact conversation, failed turn, recognized runtime state, and compatible state/history structures. Confirmation requires a valid non-empty string identifying the new turn.
- Twenty-eight AI-generated kitchen utensil sprites, parabolic flight, a stationary one-second notification, and no voice output. Locked desktops discard visuals while background sending can continue; skipped visuals are not replayed.
- Explicit installation, read-only Doctor checks, visual preview, Start/Stop entry points, and opt-in logon autostart with supervisor recovery.
- Private runtime data under `.runtime/` by default, Git ignore rules, and an allowlist requirement for release packages.
- English and Simplified Chinese documentation, contribution and security guidance, and community issue/PR templates.

### Differences from the earlier personal prototype

The earlier personal prototype could act on unresolved historical failures, included archived conversations, and could use legacy rollout events. The public release deliberately changes those defaults: baseline existing failures, exclude archived conversations, and require compatible `state_5.sqlite` **and** `thread_history_1.sqlite`. There is no legacy rollout fallback for automatic sends. Missing history is a Doctor error. Users can manually send `继续` once to resume an existing failed task.

### Known boundaries

- Undocumented desktop IPC snapshot v11 and start-turn v2 may change after a Codex upgrade; compatibility is not guaranteed.
- Codex CLI, VS Code, macOS, and Linux are unsupported.
- The available local baseline is one Windows 11 machine with Codex 26.1016.6573.0, Python 3.14.3, and Node.js 22.20. It is not cross-computer validation.
- Local candidate validation records 48 Python tests, 16 Node tests, and 26 PowerShell 5.1 checks passing, successful installation and bilingual visual smoke checks, and read-only desktop checks with zero real messages. Real sending, real lock/unlock, scheduled-task registration, and reboot recovery remain unvalidated for the public build.
- [GitHub Actions run 39750132929](https://github.com/LocusQiang/fxxk-u-tibo/actions/runs/39750132929) passed at `6a9037d` across Python 3.11–3.14 with Node.js 22 on `windows-latest`, including 48 Python tests and 16 Node tests per job, PowerShell parsing, and package construction. This run predates the added PowerShell lifecycle test script. Packaging uses an explicit allowlist; checksums accompany the corresponding GitHub Release.
