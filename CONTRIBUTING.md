# Contributing

Thanks for helping improve fxxk u tibo. English and Simplified Chinese issues and pull requests are welcome. Keep changes focused on a reproducible problem or a clearly described user need.

## Before opening an issue

Read the [README](README.md) and [compatibility notes](docs/compatibility.md). Include the project version or commit, Windows version and architecture, Codex desktop version, Python version, Node.js version, and the relevant Doctor check name/result. State whether the behavior came from a synthetic test, visual preview, or a real desktop run.

Use the bug-report template for reproducible defects and the feature template for proposals. Suspected vulnerabilities belong in the reporting process in [SECURITY.md](SECURITY.md), not a public bug report.

Do not attach raw runtime folders, conversation databases, session files, credentials, real conversation/turn/message IDs, personal absolute paths, or screenshots of private chats. Prefer a short summary and a synthetic reproduction. A private report still does not require credentials or entire chat histories.

## Local development

Use a separate writable checkout and a supported Windows environment. Run setup as described in the README to create the local virtual environment. Installation and preview do not start automatic retries. Use synthetic fixtures for development; do not point an experimental change at personal conversations merely to exercise a code path.

The existing local test entry points are:

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s . -p "test_*.py"
node --test .\test_bridge.cjs
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\test-scripts.ps1
~~~

Only run a live sending test when the operator explicitly intends to resume the affected task and understands its permissions and possible usage costs. The first-start baseline skips existing failures; test that boundary with fixtures instead of clearing personal runtime records.

## Behavioral boundaries to preserve

- The first normal Start establishes a persistent baseline. Pre-existing failures are skipped; users can manually continue an old failed task once. Setup and Preview must not send messages.
- Archived and subagent conversations are excluded. The public version has no archived-conversation opt-in switch.
- Both `state_5.sqlite` and `thread_history_1.sqlite` must have compatible structures. Missing history must be a Doctor error. Legacy rollout files must not provide an automatic-send fallback.
- Sending requires the exact current failed turn, a recognized idle runtime state, and a qualifying structured service failure. Unknown runtime or history structures block submission. A new turn must be confirmed by a valid non-empty string identifier; unknown send outcomes must not be automatically resubmitted.
- Keep durable duplicate protection and the minimum 30-second per-chat interval. Do not delete private runtime state to make a test pass.
- Send exactly `继续`, inherit conversation settings, and preserve approval boundaries. UI language must not change the sent message.
- Locked desktops discard visuals without replay; background retries can continue. A manual Stop must be respected until explicit Start or the next reboot. Autostart remains opt-in.
- Do not read `auth.json`, upload chats, add analytics, or include private runtime data in a release.

Changes to these boundaries need an explicit proposal describing the user impact and migration behavior. Do not silently loosen a submission check to accommodate an unknown Codex version.

## Pull requests and validation

Describe the problem, resulting behavior, and why the change is needed. Preserve unrelated work. Update both READMEs when user-facing behavior changes, and update compatibility notes when an interface assumption changes.

Run the smallest relevant checks for your change, then the repository's required checks. Add meaningful tests for changes to sending, baseline persistence, duplicate protection, schema handling, or lifecycle behavior. Documentation-only changes need command, link, and consistency checks; they do not require live sends.

Report actual evidence separately:

| Evidence | What to record |
| --- | --- |
| Static/document checks | Files inspected, command/link validation, and limitations. |
| Automated local tests | Exact command, result, environment, and tested revision. |
| Local desktop run | Exact versions, scenario, observed result, and remaining gaps. |
| Another machine | An actual independent environment and its result; do not relabel a second run on the same PC. |
| Release package | Allowlist and resulting archive contents, including privacy exclusions. |

Do not turn a synthetic test, preview animation, or successful Doctor probe into a claim that a real task resumed or completed. Leave unrun checks marked as not run. Test totals can change before release; do not copy stale totals into release documentation.

## Assets, dependencies, and packaging

The software uses MIT. Submit work you have the right to contribute under that license. For AI-generated images, describe their origin and license only rights you can grant; do not claim exclusive copyright in generated output. Preserve separate dependency notices.

Source users install the dependencies separately; the EXE bundles them and preserves their licenses. To build it on Windows x64, install requirements-build.txt, run python build_exe.py, then python package_release.py. The build downloads and verifies the pinned official Node archive. Build artifacts stay under build/ and dist/. Check both the source allowlist and EXE contents before publication. The historical Kenney/Three.js assets and renderer are not included in the public distribution; do not reintroduce them without a separate review of scope and licensing.

Release packages must be built from an explicit file allowlist. Exclude `.runtime/`, local virtual environments, caches, credentials, databases, session files, private diagnostics, and personal screenshots. Git ignore rules alone do not verify an archive's contents. Check the actual archive before publishing.
