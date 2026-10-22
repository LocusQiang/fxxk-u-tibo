# Changelog

Changes to Codex Auto Retry Kitchen are recorded here. Release entries describe behavior; they are not test reports.

## v0.1.0 — initial public release (pending)

Publication date and release verification are pending completion by the release maintainer. No published tag or release artifact is asserted here.

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
- Final release test counts and outcomes are pending in [the validation record](docs/compatibility.md#release-validation-record). No fixed pass count is claimed while changes and tests are still being integrated.
