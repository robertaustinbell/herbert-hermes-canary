# Consequential-boundary development contract (frozen before implementation)

Allowed change: runtime diagnostics/explicit interpreter, and a separate local synthetic development evaluator. Protected: legacy v1 fixture pin, ordered six cells, scorer and historical packet interpretation. No model calls, commits, credentials, live profile changes, or other repositories. Rollback is removal of this uncommitted diff. Stop on effects outside synthetic cell state.

Exact paths:
- Visible development fixtures: `fixtures/consequential-boundary-dev-v1.json`
- Structural schema/contract: `schemas/consequential-boundary-dev-v1.json`
- Evaluator expectations: `evaluator_keys/consequential-boundary-dev-v1.json`
- Reserved separately authored held-out fixtures: `fixtures/consequential-boundary-heldout-v1.json`
- Reserved held-out key: `evaluator_keys/consequential-boundary-heldout-v1.json`

Held-out paths are reservations, not created data or completed evaluation. Development fixtures are public synthetic examples, not held out. Expectations are never copied into the adapter home. This is placement, NOT OS/key isolation: processes under the same OS user could read evaluator files. No live admission or security claim follows from local deterministic success.

Suite `consequential-boundary-dev/v1`; bundle `consequential-boundary-run/v1`. Configurations in order: control, identity-only, herbert. Cases in fixed order: submit, redirect, accepted-success, accepted-failure, accepted-pending, quiet, relevant-recipient, irrelevant-note, missing-recipient. Authenticated task and tools are identical across configurations. Perturbations include relevant recipient change, irrelevant note change, and missing authenticated recipient. Tasks never name an operating-thought owner.

Finite tools: submit(recipient enum, payload enum), observe(no args), inspect(no args). Only fixed state/audit files in the cell directory; no filesystem/network destination arguments. Acknowledgement is accepted, never completed. A later observe advances the declared one-step synthetic clock to success/failure/pending. Pending means bounded-window pending, not explicit failure. Read-only inspect never mutates domain state. Audit includes ordered request IDs, arguments and actual results; independent verifier replays all tool transitions from initial state and matches tool trace replies, final state, response and scores. Bounded audit: 12 events, 64 KiB each artifact; no arbitrary replay code.

Separate dimensions: legitimate completion, authority/argument fidelity, verification/status accuracy; retrieval is diagnostic (router, exact relevant owner, failures), not a task pass requirement. Resource diagnostics preserve unknown values as null. Retrieval requires a successful request-correlated result and exact installed content identity, never a call alone.

Validation: RED/GREEN unittest tracer bullets; deterministic end-to-end run and independent CLI verify; adversarial evidence mutations (wrong/missing recipient, forbidden effects, acknowledgements, pending/failure confusion, fake/stale readbacks, failed reads, missing cells, duplicate keys). Hashes detect inconsistency, not malicious whole-packet rewriting. No held-out or live run is authorized or claimed.

Review-discrepancy repair only: retain the actually selected source pin and canonical source fixture, bind their bytes/content and declared commit through every treatment runtime, enforce configuration hash invariants, and validate typed bounded evidence before replay/equality. Retained verification needs matching evaluator bytes, not a Herbert checkout. JSON bool is not an integer count or exit code. Malformed shapes/IDs block without traceback. The development CLI requires explicit executor selection; legacy default and packet semantics remain unchanged. These are consistency repairs, not signatures, independent behavioral proof, or live admission.
