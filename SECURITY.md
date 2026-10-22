# Security policy

Codex Auto Retry Kitchen is an unofficial local companion. Its ability to resume a Codex task is security-relevant even though it does not read credentials or upload chats.

## Reporting a vulnerability

**GitHub private vulnerability reporting is enabled for this repository.** Use the [private vulnerability report form](https://github.com/LocusQiang/codex-auto-retry-kitchen/security/advisories/new) for suspected security issues.

1. Open the private report form and sign in to GitHub if prompted.
2. Include the affected version, impact, a minimal synthetic reproduction, and any proposed fix.
3. If you cannot access the private form, do not post exploit details or private data publicly. You may open a public issue containing only a request for a private reporting channel. Wait for the maintainer to provide one before sharing sensitive details.

No separate security email address, guaranteed response time, or bounty program is advertised. This is a community-maintained project. Public issue templates are for non-sensitive defects and feature proposals.

## Version scope

The initial public release is v0.1.0. Release validation is pending in [Compatibility](docs/compatibility.md#release-validation-record). Reports should identify the exact release or commit. No security maintenance commitment is made for the earlier personal prototype, unpublished local modifications, unsupported platforms, or unverified Codex builds.

A vulnerability in Codex itself belongs with its vendor's security reporting process; include this project only when its behavior is involved.

## Security-sensitive behavior

- Starting the watcher permits automatic submission of the literal `继续` to eligible conversations. This can consume usage and resume tools or other actions under the original conversation's permissions. The tool must not bypass approval checks.
- First normal Start persists a baseline and skips already-present failures. Archived and subagent conversations are excluded, with no public archived-conversation switch. Existing failed tasks can be continued manually by the user.
- Both state and history databases must be structurally compatible. Missing history is an error, and legacy rollout files cannot trigger automatic sends. Unknown runtime state or history structure blocks submission.
- Confirmation requires a valid non-empty string identifying the newly created turn. Pending or unknown send outcomes must never be automatically resubmitted. The journal and baseline must survive restarts.
- The bridge uses undocumented local IPC. Access to the same Windows user session and its local files is a trust boundary; this tool is not a sandbox against malicious processes already running as that user.
- A locked desktop does not suspend automatic continuation. Visuals are discarded. Sleep and shutdown prevent execution.

Useful reports include unintended continuation of old or archived tasks, duplicate sends after ambiguous results, submitting with an unknown state/schema, failure to honor Stop, accidental disclosure through diagnostics or packages, or a change that weakens approval inheritance. Use synthetic data to demonstrate these conditions.

## Data handling

The project opens Codex databases read-only and does not read `auth.json`. It does not upload chats or collect analytics. Resuming a turn still uses the Codex application's normal network and service behavior, and dependency setup downloads packages.

Private runtime data defaults to the repository's `.runtime/` directory. It includes settings, the first-start baseline, action records, logs, counters, and process state. These files can contain local paths and conversation identifiers or titles. Git ignores runtime data; release packages must use an explicit allowlist and be inspected before publication.

Do not attach credentials, raw chat histories, entire runtime directories, real identifiers, personal paths, or private-chat screenshots to either public reports or initial private reports. Share the smallest synthetic example that demonstrates the problem.

## If unintended continuation occurs

Use `Stop.vbs` to stop further monitoring. A send already underway may complete, and a task already resumed must be stopped in Codex itself. If autostart is installed, remove it with `install-autostart.ps1 -Remove` to prevent resumption after a future reboot/logon. Keep the runtime journal and baseline private and intact while inspecting the affected conversation; deleting them is not a recovery procedure.
