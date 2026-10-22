# Compatibility and validation

Codex Auto Retry Kitchen targets Windows 10/11 x64 and the Windows Codex desktop app. It uses private local interfaces. A target or a passing capability check is not a guarantee that a real continuation works on every machine or after an upgrade.

## Environment matrix

| Environment/component | Target or requirement | Available evidence | Remaining gap |
| --- | --- | --- | --- |
| Windows 11 x64 | Target | Local suites, installation, visual smoke, and read-only desktop checks on one PC | Real sending, lock/unlock, scheduler registration, and reboot behavior remain unvalidated for the public build. |
| Windows 10 x64 | Target | No separate Windows 10 result recorded here | Requires an actual Windows 10 run. |
| Codex desktop 26.1016.6573.0 | Known local baseline | Read-only connection and parsing of an actual idle, completed canonical snapshot passed | No real continuation messages sent during public-build validation. |
| Other Codex desktop builds | No compatibility guarantee | No results claimed | Check schema and IPC, then validate behavior in the intended environment. |
| Python 3.14.3 | Known local baseline | Local Python suite passed in the reported environment | Does not establish behavior on every supported Python version. |
| Python 3.11–3.14, with tkinter | Required range | Hosted CI passed on 3.11, 3.12, 3.13, and 3.14 with Node.js 22 at `6a9037d` | Synthetic CI does not validate real Codex integration or visuals on each version. |
| Node.js 22.20 | Known local baseline | Local Node suite and read-only bridge checks passed | Other runtime versions need separate evidence. |
| Node.js 22+ | Minimum requirement | Later versions not exhaustively tested | A version threshold alone is not compatibility evidence. |
| Pillow 12.2.0 | Pinned dependency | Fresh environment download/install and English/Chinese visual smoke passed | Results are from the same local PC. |
| Another computer | Not yet validated | No independent machine result recorded | Do not describe repeated runs on the same PC as cross-computer validation. |
| Windows ARM64 or 32-bit | Outside the x64 target | No support claim | No validation committed. |
| Codex CLI / VS Code extension | Unsupported | No integration support | Use the Windows desktop app. |
| macOS / Linux | Unsupported | Windows-specific desktop, lifecycle, and UI integration | No support claim. |

Python, Node.js, and Codex are separately installed. Python must include tkinter/Tcl/Tk support. Pillow is installed into the project environment and retains its separate license.

## Private interface contract

IPC means inter-process communication between the local bridge and the Codex desktop application.

| Interface | Expected form | On mismatch or uncertainty |
| --- | --- | --- |
| Desktop snapshot | Version 11 snapshot for the exact conversation | Do not submit from missing, stale, or unrecognized state. |
| Runtime state | Recognized idle state for the conversation being resumed | Active or unknown state blocks the submission. |
| Desktop history | Recognized turn-history structure identifying the latest failed turn | Unknown history structure blocks the submission. |
| Start-turn request | Version 2; inherits conversation settings; input is exactly `继续` | No alternate text or permission override. |
| Send acknowledgement | Valid non-empty string identifying the newly created turn | Missing, malformed, or ambiguous confirmation is an unknown outcome; never automatically resend it. |
| State database | `state_5.sqlite` with compatible conversation metadata and archive information | Missing or incompatible structure is an error; do not guess eligibility. |
| History database | `thread_history_1.sqlite` with compatible latest-turn status/error data | Required. Missing history is a Doctor error, and incompatible history blocks sending. |

Both local databases are read-only inputs. **There is no legacy rollout-file fallback for automatic sending.** A text mention of “503” in a conversation is not enough: a matching structured failure and a verified current failed turn are required.

These interfaces are undocumented implementation details, not a stable public API. The listed versions describe the integration's assumptions, not an OpenAI compatibility promise. Do not rename a database, edit Codex history, or weaken state checks to make an incompatible version appear supported.

## Public release versus the earlier personal prototype

| Behavior | Earlier personal prototype | Public v0.1.0 behavior |
| --- | --- | --- |
| Existing failures on first run | Could resume unresolved historical tasks | First normal Start establishes a persistent baseline and skips failures already present. Only subsequent new qualifying failures are automatically resumed. |
| Archived conversations | Included | Excluded by default; no public switch to include them. |
| Subagent conversations | Excluded | Excluded. |
| Missing indexed history | Legacy structured rollout events could be used | Both compatible databases are required. Missing history is an error; no automatic-send fallback. |
| Unknown runtime/history shape | Do not carry assumptions from prototype behavior forward | Block the current submission. |
| Unknown send outcome | No automatic duplicate should be assumed safe | Retain the unknown outcome and prohibit automatic resubmission. |

To resume a failure present before first normal Start, the user can open that conversation and manually send `继续` once. If it later produces a distinct qualifying failure while monitoring is active, that new failure can be considered normally. Setup and visual Preview do not start monitoring. The baseline persists across restarts; deleting runtime records is not a supported way to opt old tasks into automatic recovery.

## Capability checks and upgrades

From the installed project's folder, run the read-only capability check:

~~~powershell
.\.venv\Scripts\python.exe .\doctor.py
~~~

With Codex open, optionally check the local IPC connection:

~~~powershell
.\.venv\Scripts\python.exe .\doctor.py --connect
~~~

Doctor does not submit a continuation. A successful handshake proves only that the connection initialized; it does not prove snapshot parsing, start-turn compatibility, live delivery, or task completion. Its output may contain personal paths, so review it locally and share only a redacted summary.

After a Codex upgrade:

1. Stop the watcher before relying on the new build. If autostart is enabled, remove it while investigating an incompatibility so a future recovery tick or logon cannot re-enable monitoring.
2. Record the new Codex version and run Doctor, optionally with `--connect`. Treat missing history, incompatible schemas, and unknown runtime/history forms as blocking conditions.
3. Keep automatic sending stopped if the checks fail. Report the version, failing check, and a synthetic reproduction. Do not share raw databases or session data.
4. If the capability checks pass, use Preview to check rendering separately. Any live sending validation must be intentional, use a task the operator is willing to resume, and account for its permissions and usage.
5. Record the exact environment and actual observed results before making a new compatibility claim. Re-enable monitoring or autostart only when the operator intends automatic continuation.

## Lifecycle boundaries

- A confirmed retry shows one of 28 AI-generated kitchen utensils in parabolic flight and a stationary one-second reminder, without voice output. A notification is not evidence of task completion.
- Locked desktops can keep sending when Codex and the local session remain available. Visuals are dropped, not queued for replay. Sleep or shutdown prevents execution.
- Opt-in autostart triggers at user logon and checks supervisor recovery every minute. Registering it can make monitoring start on the next recovery tick in the current login session, not only after a reboot.
- Unexpected worker exits use a 3–60 second restart delay. Manual Stop remains effective until explicit Start or the next reboot. With autostart installed, monitoring can return after reboot and logon.
- Stop may allow an in-flight send to finish. It does not cancel a task already resumed inside Codex. Removing autostart does not stop an existing worker.

## Release validation record

Results reported by the maintainer and reviewers on **2026-10-22** for the **v0.1.0 candidate checkout**. Local installation, desktop, and visual results below are from one Windows 11 x64 PC with Codex 26.1016.6573.0, Python 3.14.3, and Node.js 22.20. The separately recorded hosted CI result applies to revision **`6a9037d`**; it does not establish real Codex compatibility on another PC.

| Evidence category | Result | Scope and limits |
| --- | --- | --- |
| Automated local suites | **48 Python tests and 16 Node tests passed.** | Includes a synthetic 16-project mixed-outcome scenario, 16 simulated sends while locked, journal duplicate/unknown-outcome protection, baseline persistence, missing-database and archive handling, and child-process crash recovery. Simulated sends are not real Codex messages. |
| Local PowerShell checks | **26 checks passed under Windows PowerShell 5.1** using `scripts/test-scripts.ps1`. | Covers task ownership guards, Stop/Ensure behavior, prior-boot state, mocked hidden launching, and environment restoration. No real scheduled-task registration, reboot, or sending occurred. Added after the recorded CI revision. |
| Read-only desktop checks | **Doctor `--connect` passed.** A reviewer also probed an actual idle conversation with a completed canonical snapshot; the strict parser accepted its structure. | **Zero real continuation messages sent.** Accepting the snapshot structure does not make a completed turn eligible for a retry, or prove start-turn delivery. |
| Installation | **Windows PowerShell 5.1 installation passed** in the public checkout and in a fresh allowlisted ZIP extraction under a nested path containing Chinese characters and spaces. | A fresh `.venv` and Pillow 12.2.0 were downloaded/installed. Installation started no sender and registered no scheduled task. Both runs used the same PC. |
| English visual smoke | **Passed: 88 frames; measured toast duration 1.005 seconds.** | Actual `--ui-smoke` rendering; right-to-left parabolic flight and stationary toast checks passed. `demo_only=true`, `daily_count=0`. |
| Chinese visual smoke | **Passed: 96 frames; measured toast duration 1.007 seconds.** | Actual `--ui-smoke` rendering; right-to-left parabolic flight and stationary toast checks passed. `demo_only=true`, `daily_count=0`. Neither visual run proves live sending. |
| Source package | **The source package uses an explicit 78-file allowlist**, including `scripts/test-scripts.ps1`. Fresh package installation and Demo launch passed. | For distributed archives, use the checksum provided with the corresponding [GitHub Release](https://github.com/LocusQiang/codex-auto-retry-kitchen/releases). File counts do not identify archive contents. |
| Source privacy and image metadata | **Zero findings** in the final 78-file source allowlist, including the lifecycle test script. Local documentation links also resolved. | The check searched for personal machine paths, real conversation identifiers, credential patterns, and embedded image metadata; it is not a formal security audit. |
| Static documentation | Local relative-link/anchor, PowerShell example syntax, YAML structure, bilingual behavior, and privacy checks completed. | Does not prove GitHub-rendered forms or runtime behavior. |
| Artwork privacy | All 28 current sprites and the contact sheet were visually inspected; no private information was found. | Maintainer-reported asset review; not a copyright or runtime claim. |
| Private security reporting | Enabled, confirmed through the GitHub API. | Use the private form linked in [Security](../SECURITY.md). |
| Continuous integration (CI) | **[Run 39750132929 passed](https://github.com/LocusQiang/codex-auto-retry-kitchen/actions/runs/39750132929) at `6a9037d`.** All four `windows-latest` matrix jobs used Python 3.11/3.12/3.13/3.14 with Node.js 22; each passed 48 Python tests, 16 Node tests, PowerShell parsing, and package construction. | The recorded run predates `scripts/test-scripts.ps1` and later documentation changes. Its success does not validate later revisions. [Current workflow runs](https://github.com/LocusQiang/codex-auto-retry-kitchen/actions/workflows/test.yml) provide revision-specific results; hosted synthetic tests do not establish real Codex behavior on a second computer. |
| Real sending / real lock-unlock | **Not run for the public build.** | Unit-test lock behavior and visual smoke do not substitute for a real locked-desktop sending test. |
| Scheduled-task registration / reboot | **Not run for the public build.** | Child-process recovery tests and installer checks do not establish actual scheduler registration or reboot recovery. |
| Another PC / Windows 10 | **Not validated.** | A second folder or fresh ZIP on the same PC is not a second machine. |

These results establish only the scenarios and revisions stated. They do not establish completion of an original user task, compatibility with other Codex builds, or successful validation of a later revision.
