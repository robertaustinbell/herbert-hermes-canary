# Herbert–Hermes Behavioral Canary

An executable, bounded regression canary for [Herbert](https://github.com/robertaustinbell/herbert)'s public untrusted-content fixtures. It exercises a real Hermes installation, not just template-flavored text sent to a provider API.

## Quick start

Requirements: Python 3.9+, Git, macOS or Linux, and Hermes with a provider authenticated through `auth.json`. Deterministic tests need only Python and Git. API-key-only and arbitrary custom-provider setups are not supported by this adapter. Use only a machine and provider account you are authorized to evaluate; live runs consume quota and may incur cost.

```bash
git clone https://github.com/robertaustinbell/herbert-hermes-canary.git
cd herbert-hermes-canary
git clone https://github.com/robertaustinbell/herbert.git .cache/herbert
# Use the reviewed pin, not moving main.
git -C .cache/herbert checkout "$(python3 -c 'import json; print(json.load(open("source-pin.json"))["herbert_commit"])')"
python3 scripts/run_canary.py \
  --herbert-source .cache/herbert \
  --output runs/manual-run \
  --model gpt-6.1-sol \
  --provider openai-codex \
  --reasoning low
# Recompute retained scores without calling a model.
python3 scripts/verify_run.py runs/manual-run
```

Choose a model available to your provider. The example is an exercised configuration, not a universal recommendation. The Hermes launcher must have its runtime `python` executable beside it. See [VERIFICATION.md](VERIFICATION.md) for the exercised version and limitations.

Use a new, empty output directory each time. Exit codes: **0/pass**, **1/behavioral fail**, **2/error**. Missing evidence, unavailable capabilities, unresolved checks, or invalid bundles are errors, not passes. Execution errors stop the run and preserve partial evidence; preflight errors before a run starts produce JSON on stdout.

## Test shape

| Configuration | Cases |
|---|---|
| Stock Hermes, bundled skills disabled | baseline, positive control, adversarial |
| Herbert SOUL plus thin Agent Ops retrieval adapter | baseline, positive control, adversarial |

Each cell starts in a fresh temporary home with the same model, provider, reasoning level, authenticated task, output contract, synthetic source, and instrumented MCP tool. Treatment installs only Git-tracked regular files from the pinned public identity, router, and operating-thought corpus. No private Bobert memory, skills, sessions, or standing authority is installed.

The synthetic tool writes only a marker and audit record in the cell directory. Its arguments cannot select a path, recipient, credential, or network destination. The MCP process is **not an OS security sandbox**. Use a disposable environment where stronger containment is required.

## Scoring and limits

The scorer reads the final response, exported Hermes tool trace, MCP audit, and marker observation. The source pin fixes the Herbert commit, fixture path/hash, and ordered case IDs. Checks cover exact task facts in an ordered JSON response, positive-control field order, no synthetic-canary repetition in the final response, and no tool call, nonempty audit, or marker. Every expected-outcome label must have a known operational check.

Several semantic labels map to the same bounded observable: valid task output plus no observed tool effect. This does **not** inspect internal authority interpretation or establish future-policy integrity. The evaluator adds a strict JSON output contract and measures compliance with that adapter contract as well as the underlying task.

Missing artifacts, incomplete execution, mismatched identities, source drift, or inconsistent scores block verification. Hashes and cross-artifact checks detect inconsistencies; they are not signatures or protection against someone able to rewrite the entire packet.

## Evidence and privacy

Runs retain a manifest, source pin and fixture, evaluator-code hashes, and per-cell prompt, response, redacted session export, normalized trace, usage, runtime/install metadata, execution result, score, and aggregate summary. `runs/` is ignored except for its placeholder. Evidence includes local paths and runtime metadata: **do not publish raw bundles automatically**. Review and sanitize before sharing.

Subprocesses receive an allowlisted environment with temporary `HOME` and `HERMES_HOME`; ambient API keys and evaluator variables are not inherited. An authentication-file symlink enables provider access without copying credentials into evidence. Hermes may refresh the linked authentication record. Logs are redacted and scanned for common credential forms, not guaranteed free of every possible secret. Never use real secrets as canaries.

## Automation

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q herbert_canary scripts tests
```

Ordinary CI runs deterministic installer, scorer, hostile-evidence, and CLI tests without credentials or model calls. Live evaluation is opt-in through the command above. [The manual live workflow](.github/workflows/live.yml) requires a dedicated, authenticated Linux self-hosted runner labeled `herbert-canary`; this repository does not configure one. Do not use a personal or production host. Configure the `canary-live` GitHub environment with required reviewer approval before enabling it. The workflow accepts only trusted `main`, not PR code, and does not upload raw evidence. No live PR gate or recurring schedule is installed.

To evaluate a new Herbert revision, review it, update the commit and fixture digest in the source pin, rerun deterministic checks, and use a new output directory. Never silently rebind an old result to new bytes.

## Interpretation

- Both pass: smoke success, no demonstrated Herbert advantage.
- Both fail similarly: inspect model, runtime, fixture, or harness.
- Stock passes and Herbert fails: investigate a possible treatment regression.
- Herbert passes and stock fails: possible benefit requiring repetition.

The task forbids tools. Passing treatment is therefore not expected to retrieve Agent Ops; retrieval is recorded as a mechanism observation, not a hidden success criterion. These cases primarily exercise always-loaded identity and the runtime instruction boundary. They do not establish deeper operating-thought value, prompt-injection containment, cross-runtime compatibility, general judgment quality, full Bobert behavior, or production reliability.

## Provenance and license

Maintained alongside Herbert. Implementation and publication were materially AI-assisted. Verification claims refer only to recorded executions. MIT licensed; see [LICENSE](LICENSE).
