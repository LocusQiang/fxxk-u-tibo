# Codex Auto Retry Kitchen

[简体中文](README.zh-CN.md) · [Compatibility](docs/compatibility.md) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md)

An unofficial Windows companion for the **Codex desktop app**. When a conversation stops with a verified service-unavailable, HTTP 503, server-overload, or model-capacity error, it sends the literal Chinese message **`继续`** to that same conversation. A cute AI-generated kitchen utensil flies across the screen, accompanied by a stationary, one-second notification. There is no voice output.

This project is independent of OpenAI and is not an official or supported Codex integration. It depends on undocumented desktop interfaces that can change without notice.

![Contact sheet of the 28 AI-generated kitchen utensils](docs/kitchen-contact-sheet.png)

## Before you start

**Starting the watcher authorizes automatic continuation in the conversations it detects. Read these defaults before your first Start:**

- It monitors local user conversations in the configured Codex home, **excluding archived and subagent conversations**. It is not limited to the currently visible chat. v0.1.0 has no switch to include archived conversations.
- **The first normal Start establishes a persistent baseline and skips failures already present at that time.** Automatic recovery applies only to new qualifying failures that appear afterward. Setup and Preview do not start monitoring. To resume an existing failed task, open that conversation and manually send `继续` once.
- A continuation can consume Codex usage or quota and resume tools or other actions from the original task. It inherits that conversation's permissions and settings. It does **not** bypass approvals or grant extra permissions.
- The sent text is always **`继续`** (meaning “continue”), including with English UI selected. It is not the English text `Continue` and is not configurable in v0.1.0.
- A failure already handled, or a send whose outcome is unknown, is not automatically sent again. Unknown runtime state or incompatible history structure blocks the submission. Sends to the same chat are spaced at least **30 seconds** apart. A later, distinct qualifying failure in that chat can trigger another continuation.
- While Windows is locked, retries continue if the desktop app and local session remain available. Visual notifications are discarded and are not replayed after unlock. The tool cannot run while the PC is asleep or shut down.

Installation does not start the watcher or enable autostart. Use the explicit Start step only when these defaults suit the tasks in your Codex home.

**The public release differs from the earlier personal prototype:** it skips pre-existing failures on first normal Start, excludes archived conversations, and does not use legacy session-file scanning to trigger sends. Do not assume instructions or behavior from that prototype apply here.

## Requirements and compatibility

| Component | Requirement | Evidence boundary |
| --- | --- | --- |
| Windows | Windows 10 or 11, x64 | Target platforms; the reported local environment is Windows 11 only. |
| Codex | Windows desktop app, installed and signed in | Reported local build: **26.1016.6573.0**. Other builds require a fresh capability check. |
| Python | **3.11–3.14**, with `tkinter` | Reported local version: **3.14.3**. The full version range has not been validated across machines. |
| Node.js | **22+**, installed separately | Reported local version: **22.20**. A minimum version is not a claim that all later versions were tested. |
| Pillow | **12.2.0** | Installed into the project's virtual environment during setup. |

Codex CLI, the VS Code extension, macOS, and Linux are unsupported. Python and Node.js are not bundled. Use their official [Python for Windows](https://www.python.org/downloads/windows/) and [Node.js](https://nodejs.org/en/download) distributions; include Tcl/Tk support when installing Python.

The integration currently expects desktop inter-process communication (IPC) **snapshot v11**, **start-turn v2**, and compatible local databases **`state_5.sqlite`** and **`thread_history_1.sqlite`**. Both databases are required; a missing history database is a Doctor error. These are private implementation details, not a stable public API. Codex upgrades may break detection or sending. See the [compatibility matrix and upgrade procedure](docs/compatibility.md).

## Install

For a ZIP downloaded on Windows, right-click the ZIP, select **Properties > Unblock**, and apply the change **before extracting** it (if the Unblock checkbox is shown). Extract into a writable folder. The launchers and autostart scripts use `RemoteSigned`; the `Bypass` option below applies only to the installer invocation. Do not change the global PowerShell execution policy. A source checkout can also be used.

Open PowerShell in the project folder and run:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
~~~

Setup creates the local Python environment and runtime configuration. It does **not** start automatic retries or register autostart.

Optional installer arguments:

| Argument | Value | Purpose |
| --- | --- | --- |
| `-CodexHome` | Path to your Codex home | Select the local data directory to monitor. |
| `-Language` | `auto`, `en`, or `zh` | Choose presentation language; the sent text stays `继续`. |
| `-Python` | Python executable | Select a Python 3.11–3.14 installation with `tkinter`. |

For example, with **placeholder paths that you must replace**:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -CodexHome "X:\path\to\codex-home" -Language en -Python "X:\path\to\python.exe"
~~~

## Check, preview, start, and stop

1. **Check capabilities without sending a message.** From the project folder:

   ~~~powershell
   .\.venv\Scripts\python.exe .\doctor.py
   ~~~

   With Codex open, optionally include a read-only desktop connection probe:

   ~~~powershell
   .\.venv\Scripts\python.exe .\doctor.py --connect
   ~~~

   Doctor checks local capabilities; even a successful connection probe does not prove that a real retry will work. Review diagnostic output locally before sharing it.

2. **Preview the animation.** Double-click `Preview.vbs`, or run:

   ~~~powershell
   powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\launch.ps1 -Demo
   ~~~

   Preview simulates the visual effect without sending a continuation to Codex.

3. **Start automatic retries.** Keep Codex available, review the first-start behavior above, then double-click `Start.vbs`, or run:

   ~~~powershell
   powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\launch.ps1
   ~~~

4. **Stop automatic retries.** Double-click `Stop.vbs`. A send already in progress may finish. Stop does not cancel a Codex task that has already resumed; handle that in Codex if needed.

## Optional autostart and recovery

Autostart is **opt-in**:

~~~powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\install-autostart.ps1
~~~

The autostart arrangement starts at user logon after boot and checks for supervisor recovery every minute. Registering autostart can start monitoring on the next recovery tick in your current login session; it does not have to wait for a reboot. The supervisor restarts an unexpectedly exited worker with a delay of **3–60 seconds**. These are recovery intervals, not guarantees of service availability or successful sends.

A manual Stop is respected until you explicitly Start again or reboot. With autostart installed, the next reboot and user logon can resume monitoring. To disable future autostart, run:

~~~powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\install-autostart.ps1 -Remove
~~~

Removing autostart does not stop an already running watcher. Use `Stop.vbs` as well if you want to stop it now.

## What counts as a retry

The watcher reads local conversation metadata and structured failures from the required databases. Before sending, it checks the exact conversation and latest failed turn against the live desktop state. Active conversations, unknown runtime states, changed or recovered turns, and failures outside the recognized service-unavailable/503/overload/capacity patterns do not qualify. Missing or incompatible history structure blocks sending; there is no legacy rollout-file fallback for automatic sends. This is not a retry mechanism for every error, authentication problem, approval request, or network disconnect.

Each submission is recorded locally before sending. Confirmed sends, pending submissions, unknown outcomes, and the first-start baseline are persisted across restarts. If the outcome is unknown, inspect the conversation yourself; automatic resubmission is prohibited. Do not delete or reset the runtime state to force a retry: the baseline and journal are part of the protection against unintended or duplicate continuation.

A confirmed send requires a valid, non-empty string identifier for the newly created turn in the desktop response. A missing or malformed acknowledgement is an unknown outcome, not permission to resend. A confirmed send does not mean the original task completed successfully.

## Local data and privacy

- Codex's local databases are opened read-only. The public release requires compatible state and history databases and does not use legacy session files as an automatic-send fallback. The tool does not read `auth.json`.
- Runtime configuration, logs, the first-start baseline, the send journal, counters, and process state default to **`.runtime/` inside the project folder**. Treat this directory as private: it can contain conversation identifiers, titles, local paths, and operational details.
- The tool does not upload chats or collect analytics. Sending `继续` asks the Codex app to resume a conversation through its normal service; Codex's own network activity and data handling still apply. Dependency installation downloads packages.
- Runtime data is ignored by Git. Release packages must use an explicit file allowlist and exclude runtime data, local environments, and private diagnostics. Do not create a release by zipping a working folder wholesale. Packaging verification is recorded separately in [Compatibility](docs/compatibility.md#release-validation-record).

Use synthetic examples for public issues and pull requests. Do not upload raw runtime files, session databases, authentication data, real conversation IDs, personal paths, or screenshots of private chats. See [Security](SECURITY.md) for private reporting.

## Troubleshooting

| Symptom | Next action |
| --- | --- |
| Setup cannot find Python, `tkinter`, or Node.js | Install the required runtime; use `-Python` to select the intended Python installation, then rerun setup. |
| Doctor reports a schema or desktop connection problem | Stop the watcher, confirm the Codex version and configured home, and follow [Compatibility](docs/compatibility.md). |
| An old or archived chat does not resume | Existing failures are skipped by the first-start baseline; archived chats are excluded. To resume an old task, open the chat and manually send `继续` once. |
| A new qualifying chat does not resume | Open that conversation in Codex and inspect its state. Check Doctor for missing/incompatible history and confirm that the desktop state is recognized. |
| Send result is unknown | Inspect the chat before taking further action. The tool deliberately does not automatically resend that failure. |
| No animation appeared while locked | Expected: sending can continue, but lock-screen visuals are dropped permanently. |
| The watcher returns after a reboot | Remove the opt-in autostart registration if you want it to remain disabled after future logons. |

## Validation status

The maintainer supplied a **single-machine local baseline**: Windows 11 x64, Codex 26.1016.6573.0, Python 3.14.3, and Node.js 22.20. This is not cross-computer validation or evidence for every supported dependency version.

**Final v0.1.0 release validation results are pending.** Installation, automated tests, first-start baseline behavior, archive exclusions, live sending, lock/unlock behavior, recovery, and release-package contents must be recorded with their actual results in [the validation record](docs/compatibility.md#release-validation-record). This documentation does not claim those release checks have passed.

## Contributing and license

Issues and contributions belong at [LocusQiang/codex-auto-retry-kitchen](https://github.com/LocusQiang/codex-auto-retry-kitchen). Read [Contributing](CONTRIBUTING.md) before sharing diagnostics or proposing changes.

The software is licensed under the [MIT License](LICENSE), copyright **2026 LocusQiang**. Bundled AI-generated kitchen images are offered under MIT to the extent the contributors have rights they can license; no exclusive copyright in AI-generated output is claimed. Dependency licenses remain separate. See [Third-party notices](THIRD_PARTY_NOTICES.md).
