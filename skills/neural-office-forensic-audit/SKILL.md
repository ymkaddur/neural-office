---
name: neural-office-forensic-audit
description: Audit or diagnose Neural Office authority, recovery, file boundaries and process ownership with reproducible fault experiments. Use for requested reliability or security investigations, not routine visual edits.
---

# Neural Office forensic audit

Establish the audited commit and real entry point first. A reference protocol, fixture reducer and operational controller are different subjects; a guarantee in one is not evidence about another.

## Scope and evidence

- Name the actor, their control, the asset and the crossed trust boundary. Hostile source content is in scope; an administrator replacing the application and its database is not an unprivileged remote attacker. A Windows Job owns processes; it does not itself sandbox filesystem or network access.
- Do not satisfy a requested minimum number or severity of findings by inventing them. Separate security exposure, availability defect, acknowledged limitation and product gap.
- Use the current contract and its counter-evidence. A retry window is not necessarily a total deadline. An advisory report's accepted integrity is not proof that a model's prose is correct.
- Record each material claim as OBSERVED, VERIFIED, INFERRED, HYPOTHESIS or UNKNOWN, with commit/file/line or a saved experimental result. Severity must name the conditions that make the impact possible.

## Experiments that exposed previous blind spots

Use synthetic inputs and temporary state; never run an experiment against the user's real ledger, witnesses, model processes or backups. Preserve baseline failure before changing production.

- Pause the runner between durable reservation, lease acquisition, controller construction and process launch. Race recovery and restoration against each pause. Checking that no child process exists is insufficient evidence that no live owner can still launch one. A generation recheck followed by launch leaves another race unless an ownership mechanism spans both operations.
- Interrupt initial witness enrollment and migration before, during and after commit. Test a real process exit as well as exceptions. A witness left empty is distinct from a valid witness; never delete or replace valid evidence to make the test pass or restore quota.
- Inject duplicate commands, lost responses after commit, stale results and restart. Verify identity, content binding and preserved consumption, not merely a disabled button or an in-memory counter.
- After adding an execution lock, replay an already terminal attempt while an unrelated attempt runs. A duplicate that only returns its confirmed result must not become a new admission or an unnecessary busy error. Match lock bookkeeping to the OS primitive: a thread-owned recursive mutex needs a thread-level reentry check, not only an execution-context variable.
- For excluded paths, assert rejection before resolve/stat/open. A check after resolving a UNC path can be too late. Lexical rejection alone does not prove that junctions or mapped drives cannot reach a network.

Use events/barriers for event order rather than sleeps as the only synchronization. Keep artifacts and diagnostic fields sufficient to replay the experiment without exposing personal paths or content.

Close experimental resources explicitly. A SQLite connection used as a context manager commits/rolls back but does not close itself; use explicit closing when a temporary database must be removed. A fixture cleanup failure is evidence about the fixture first, not automatically about production.

## Intervention and publication

For each fix, give the smallest demonstrated causal chain, a competing explanation and an observation that would refute the diagnosis. Preserve the reproducer as a meaningful regression. Test the relevant existing behavior, including abandonment, retry and resource cleanup; do not broaden unrelated modules.

Before calling a correction complete, run its failing baseline and passing patched case, required suites, and review the final diff. Record unresolved assumptions. A numeric confidence score, if requested, is subjective and scoped to the reproduced mechanism.

Publishing requires task authorization. Use only reviewed public files and synthetic evidence; inspect commit author AND committer identity. Do not expose raw logs, state, credentials or private correspondence. Verify the remote commit and checks after publication. This skill does not authorize contacting third parties.
