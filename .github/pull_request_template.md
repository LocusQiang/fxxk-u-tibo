## Problem and resulting behavior

Describe the concrete problem and what this change does for the user. Include a small before/after example when helpful. Link a public issue only if it contains no sensitive information.

## Validation

List the exact checks you actually ran, their results, the tested environment/revision, and any checks not run. Separate static review, synthetic tests, Preview/Doctor, and intentional live desktop runs. A successful send does not prove task completion; repeated runs on one PC do not prove cross-computer compatibility.

## Scope and review notes

Explain changes to public behavior, dependencies, licenses, or packaging. State any remaining uncertainty and how to revert the change when relevant.

- [ ] The change is focused and preserves unrelated work.
- [ ] Both READMEs and compatibility/changelog entries are updated where behavior changes.
- [ ] First-start baseline, archived/subagent exclusion, strict state/history checks, and unknown-outcome duplicate protection are preserved, or any proposed change is explicitly explained above.
- [ ] Approval inheritance, the fixed `继续` message, the per-chat interval, and opt-in lifecycle behavior are preserved, or any proposed change is explicitly explained above.
- [ ] No raw logs, runtime state, credentials, databases, session files, real conversation IDs, personal paths, or private-chat screenshots are included.
- [ ] Any added assets/dependencies have provenance and applicable license notices; AI-generated assets make no exclusive-copyright claim.
- [ ] Validation statements describe actual results and limitations; unrun checks are marked as such.

For documentation-only changes, state which behavioral checks are not applicable. For a security fix, follow SECURITY.md before publishing sensitive details here.
