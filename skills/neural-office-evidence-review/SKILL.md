---
name: neural-office-evidence-review
description: Review Neural Office product claims, UI prototypes and resource evidence before declaring a milestone ready. Use for acceptance audits and comparative research, not as a generic visual design style guide.
---

# Neural Office evidence review

Start from one user task and a predeclared result criterion. Record which steps execute real work, which are fixtures and which are proposals. Keep implementation detail out of the normal user journey unless it changes a meaningful decision.

## Claims that need separate proof

- A polished scene is not an integrated workflow. Follow the user's input through authorization, execution, result, closing, reopening and recovery. If no transport exists, report that gap instead of treating shape validation as permission enforcement.
- Attempts, internal iterations, model calls and accepted reports are distinct quantities. Do not relabel one to make a progress indicator look complete.
- A report recomputed by the same static checker proves consistency with that checker. It does not establish independent semantic correctness or the quality of model commentary. Use an external rubric or held-out expected results for utility.
- Test counts are inventory, not coverage. Report the invariants and failure windows exercised. Read the actual current CI results; avoid duplicated counts in changing README prose.

## UI review from demonstrated mistakes

Check the finished-result composer with no new text, with explicit follow-up text and after failure/cancellation. Confirm that no accidental resend consumes another attempt.

Check the transition from an open narrow-screen navigation drawer to a wide layout: the workspace must become interactive and focus must remain visible. Inspect stop confirmation and the composer at short/narrow viewports, not only the main screenshot. For dividers, distinguish desired width from effective width; check capture cancellation, persistence failure and keyboard behavior.

These are risk-directed examples, not a demand to redesign every component or claim universal accessibility. Record measured CSS viewport sizes and distinguish DOM assertions from visual inspection and real assistive-technology tests.

## Resource and reference discipline

Compare equivalent production builds and state the byte/compression method. Separate JS heap, process working set, committed memory, CPU time and GPU/VRAM. Short idle samples do not establish leak freedom, sustained latency or total application RAM. A smaller shell does not include the Python runtime or model weights automatically.

Pin external code to commits and describe only mechanisms actually inspected. Separate official documentation from executed tests and marketing. Repository lists, university rankings, likes and model-generated scores are not user research. Do not invent customer consensus or comparative performance. Check provenance before copying code or assets; learning a principle does not require copying an implementation.

## Exit and identity

Close a milestone only when its stated task and acceptance evidence exist. Keep visual acceptance, security, utility and performance as distinct outcomes. If users have not tested it, label any explanation of their perception as an inference.

Prefer removing an unsupported promise, duplicate definition or unnecessary option to adding another abstraction. A useful identity is a promise the current workflow can demonstrate; uniqueness in the market remains a hypothesis until researched and tested. End with the next discriminating experiment, not an expanding feature list.
