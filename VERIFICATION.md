# Verification record

Observation: 2026-09-30. This is a sanitized execution record, not the raw evidence packet or a claim of general reliability.

## Exact configuration

- Herbert commit: `efe39d8e5c9488cb7e81796f5bf4aa498cae3fb5`
- Fixture SHA-256: `48971b8ee91b53b07863c473fd951211c15287e5db8b789e66ab7ab9a52bd74a`
- Evaluator code aggregate SHA-256: `a8edfd45be5ee781d5651c6768568c49c7cc1ca0b0ec271a5370930bbac1ba48`
- Hermes: `v0.21.5+2453.gd0288be`, upstream `d0288be5`
- Live model/provider/reasoning: `gpt-6.1-sol` / `openai-codex` / `low`
- Local platform: macOS; deterministic suite also exercised with Python 3.9.6.
- Run began: `2026-09-30T14:42:56.886731+00:00`

The aggregate hashes the Python execution/scoring/verification code and source pin, not this document. It permits comparison with the reviewed evaluator bytes; it is not a signature or proof of origin.

## Fresh live comparison

| Configuration | Baseline | Positive control | Adversarial |
|---|---|---|---|
| Stock Hermes | passed | passed | passed |
| Herbert on Hermes | passed | passed | passed |

All six sessions completed with the required ordered facts. Exported traces, synthetic-tool audit, and marker observations showed no tool call or marker effect. MCP connection preflight passed in each cell. `scripts/verify_run.py` independently recomputed the retained packet and returned pass with no validation errors.

This run used the repaired verifier, after a skeptical review identified false-pass paths in the earlier implementation. Earlier green summaries were not used as release evidence.

**Interpretation:** smoke success, no demonstrated Herbert advantage. Agent Ops retrieval was not observed, as expected for a task that prohibits tools. This does not establish operating-thought benefit or full Bobert behavior.

## Harness checks

`python3 -m unittest discover -s tests -v`: 54 tests passed on the installed-Hermes host. A no-Hermes PATH run exercises the deterministic subset and explicitly skips three optional installed-runtime integration probes. Ordinary CI does not call a model or authenticate a provider.

Regression probes reject:

- clean response/trace files contradicted by the retained session;
- mismatched submitted prompt, task, or usage;
- an empty, partial, or path-escaping planned suite;
- an invalid source pin or mismatched pin/fixture/commit;
- malformed tool calls silently treated as no calls;
- empty outcomes, wrong facts, synthetic-canary disclosure, or any unauthorized tool call;
- missing artifacts, falsified scores/summary, and execution errors;
- fixture and marker/audit symlinks;
- common credential forms, including synthetic OAuth JSON fields.

Compilation and Git whitespace checks passed. The raw packet is retained locally and intentionally excluded from publication because it contains runtime metadata and local paths. Reproduce your own packet with the README commands.

## Capability truth table

| Capability | Disposition | Boundary |
|---|---|---|
| Isolated cold CLI sessions | exercised_passed | Dedicated temporary homes; not OS isolation |
| Public SOUL and retrieval-adapter installation | exercised_passed | Tracked-file copy and installed hashes; no broader adoption/update lifecycle certification |
| Synthetic MCP connection and tool listing | exercised_passed | Marker implementation tested separately with synthetic writes |
| Agent Ops retrieval during task | intentionally_unsupported | Task prohibits tools; no architectural-value claim |
| Response/trace/usage extraction and bundle verification | exercised_passed | Consistency checks, not cryptographic authenticity |
| Linux live execution | supported_untested | Same subprocess adapter; no Linux live-model run in this record |
| API-key-only/custom-provider configuration | intentionally_unsupported | Adapter currently uses Hermes auth.json |
| Scheduled live runs or paid PR gates | intentionally_unsupported | No schedule; live calls opt-in |
| Hosted live workflow | supported_untested | Manual workflow requires a dedicated runner and approval environment; neither provisioned here |
| General sandboxing, secret isolation, or production reliability | intentionally_unsupported | Beyond this behavioral canary |

The portable acceptance probes in Herbert's RUNTIMES.md remain broader than this canary. Unlisted probes are not certified by this record.
