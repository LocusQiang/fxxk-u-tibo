# Compatibility and validation

Codex Auto Retry Kitchen targets Windows 10/11 x64 and the Windows Codex desktop app. It uses private local interfaces. A target or a passing capability check is not a guarantee that a real continuation works on every machine or after an upgrade.

## Environment matrix

| Environment/component | Target or requirement | Available evidence | Remaining gap |
| --- | --- | --- | --- |
| Windows 11 x64 | Target | Maintainer-reported local environment on one PC | Final public-release scenarios are pending below. |
| Windows 10 x64 | Target | No separate Windows 10 result recorded here | Requires an actual Windows 10 run. |
| Codex desktop 26.1016.6573.0 | Known local baseline | Maintainer-reported use on that Windows 11 PC | Revalidate the final public-release changes. |
| Other Codex desktop builds | No compatibility guarantee | No results claimed | Check schema and IPC, then validate behavior in the intended environment. |
| Python 3.14.3 | Known local baseline | Maintainer-reported environment | Final release results pending. |
| Python 3.11–3.14, with tkinter | Required range | Full version range not exercised here | Runtime availability and behavior need checks per environment. |
| Node.js 22.20 | Known local baseline | Maintainer-reported environment | Final release results pending. |
| Node.js 22+ | Minimum requirement | Later versions not exhaustively tested | A version threshold alone is not compatibility evidence. |
| Pillow 12.2.0 | Pinned dependency | Declared release dependency | Installation and rendering results pending. |
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

**Final release validation results are pending.** The reported single-PC environment above is context, not a completed validation record for the final public release. Do not infer final test totals or passed release checks from this documentation.

Fill in the tested release/commit, date, environment, exact check or scenario, observed result, and remaining limitations. Keep private evidence local; use sanitized summaries or synthetic artifacts in public records. Distinguish these evidence types:

| Evidence category | Required check or scenario | Status |
| --- | --- | --- |
| Static documentation | Commands, links, bilingual behavior, license boundaries, and privacy wording | Local documentation checks completed; final release review pending. |
| Artwork privacy review | Current 28 sprites and contact sheet | Maintainer reports visual inspection completed with no private information found. This does not establish runtime behavior or legal ownership. |
| Private security reporting | Repository reporting configuration | Maintainer confirmed enabled through the GitHub API; private report form is linked in SECURITY.md. |
| Automated local tests | Final Python and Node test suites at the release revision | Pending final run and results; no fixed total claimed. |
| Fresh installation | Setup, dependency checks, configuration, and no automatic start/autostart | Pending. |
| First normal Start | Persist baseline, skip existing failures, process only later new qualifying failures | Pending. |
| Restart persistence | Preserve baseline, pending/unknown records, and duplicate protection | Pending. |
| Eligibility | Exclude archived/subagent chats; no archived opt-in switch | Pending. |
| Strict compatibility | Missing history is an error; unknown runtime/history and incompatible schemas prevent submission | Pending. |
| Sending and acknowledgement | Exact `继续` input, inherited settings, new-turn string confirmation, no unknown-outcome resend, at least 30 seconds per chat | Pending. |
| Visual preview | Sprite rendering and stationary one-second text; no message sent | Pending. |
| Live desktop behavior | Intentional real continuation, lock/unlock visual discard, no replay | Pending; synthetic checks cannot substitute. |
| Lifecycle | Start/Stop, in-flight send handling, opt-in autostart/removal, recovery, reboot boundary | Pending. |
| Release artifact | Inspect actual allowlisted package; exclude runtime data, personal files, and separately installed dependencies | Pending. |
| Additional machine / Windows 10 | Actual separate-machine and OS evidence | Not yet recorded. |
| Original task outcome | Whether a resumed user task completed acceptably | Not implied by a successful send or any tool test. |

Successful unit tests, a Doctor probe, and a generated release archive each establish only their own checked scope. They do not establish cross-computer support or completion of a user's original task.
