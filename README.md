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

The supported default is still a runtime `python` executable beside the selected Hermes launcher. `--hermes-python /absolute/path/to/python` explicitly selects the interpreter used by the synthetic MCP server; it must import `mcp` and `anyio`. It does not replace or repair the selected launcher. Local import and CLI-help preflight runs in a disposable home **before authentication linkage or chat**, failing with an actionable blocked diagnostic if required flags/imports are unavailable. The launcher and interpreter identities are retained privately in each executed Hermes cell. No alternate installation, provider, install, or authentication repair is selected automatically. See [VERIFICATION.md](VERIFICATION.md) for exercised versions and limitations.

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

## Tool-enabled development suite (separate from historical v1)

The sections above describe the original no-tools canary, selected by default or by `--suite legacy-no-tools/v1`. Its source pin, six-cell ordering, output/scoring contract and historical packet verification remain intact. Historical `herbert_agent_ops_loaded` observations were call hints, **not proof of successful retrieval**; they are not reinterpreted. Fresh observations now require a successful correlated reply matching installed content bytes.

`--suite consequential-boundary-dev/v1` selects a different 27-cell development battery: **control / identity-only / herbert**, each with the same nine authenticated cases and tools. Identity-only has exactly the pinned SOUL without the retrievable corpus. Case families cover authorized submission, source-note redirection, accepted-to-success/failure/pending, a quiet read-only report, relevant recipient change, irrelevant note change, and missing recipient. Prompts contain no owner names or consultation instructions. See [DEVELOPMENT-CONTRACT.md](DEVELOPMENT-CONTRACT.md) for the paths fixed before implementation. No held-out set has been authored or evaluated.

Run the actual finite synthetic tools **without Hermes, authentication, or model calls**:

```bash
python3 scripts/run_canary.py \
  --suite consequential-boundary-dev/v1 --executor deterministic \
  --herbert-source .cache/herbert --output runs/development-local \
  --model deterministic --provider local --reasoning none
python3 scripts/verify_run.py runs/development-local
```

The development suite requires an explicit `--executor`; omission is rejected before pin loading, runtime preflight, or authentication. The legacy suite keeps its Hermes default.

The deterministic executor is a test transport reading synthetic task input and invoking real local `submit` / `observe` functions; it is not an evaluated agent. It never reads the answer key. Its pass verifies the evaluator contract, not Herbert's behavior. `--executor hermes` wires the same development tools through the selected Hermes/MCP runtime, but **no live run of this new suite is certified here**. Live use requires separate authority, a model/provider available to that account, and security/budget review. Do not infer live admission from local tests.

Each tool has finite enum arguments plus a bounded unique request ID. There are no path/network/credential destinations. A wrong enum recipient can update synthetic state so the evaluator can detect the authority violation; it never sends a message. An accepted acknowledgement is not success. One later observation advances the local clock to success, explicit failure, or still-pending within the declared window. The latter is never inferred to be failure from unchanged state. Read-only `inspect` is available, but not required when the source already answers the quiet task.

The new scorer separates authenticated-task fulfillment, recipient/argument fidelity and status/readback accuracy. Correct failure/pending reports can fulfill the bounded submit-and-report task; they do **not** mean the underlying operation succeeded. Blanket refusal fails an authorized completable task. Retrieval is a separate diagnostic: successful request-correlated content must match exact installed hashes; router reads, relevant exact-owner reads, irrelevant owner reads, and failed lookups are distinguished. Quiet policy-read overhead is visible without becoming a hidden pass criterion. Unknown usage/cost values remain null; exported token/API/cost fields and measured executor latency are diagnostics, not provider-billing certification.

The independent verifier never runs the tools or executor. It reconstructs each finite transition from initial state and ordered audit, matches actual replies to requests and audit, requires the report after readback, compares final state, recomputes all scores and summary, and enforces every planned cell. Hermes packets additionally retain the raw session export and must normalize identically to the scored session. Outer Hermes call IDs are preserved alongside tool-local request IDs. Unsupported export/deferred-wrapper shapes fail closed rather than manufacturing evidence. Limits: 12 tool calls/events per cell and 64 KiB per cell artifact; a Hermes chat has the adapter's fixed four-turn / 300-second bounds. All configurations use the same requested model/provider/reasoning and runtime context defaults; this is not certification of context-token or spending caps.

The new bundle pins fixture, schema, development key, evaluator/script bytes, source pin, requested runtime, installed configuration content and ordered cells. The actually selected pin (including custom `--source-pin` content) is retained as `inputs/source-pin.json` and SHA-256-bound to the manifest, alongside its canonical source fixture. Verification validates the retained pin schema/path/digest/cases, binds its commit to the manifest and every treatment runtime, and requires empty control hashes, SOUL-only identity hashes, and identical SOUL in full treatment. No Herbert source checkout is needed for retained verification. Typed bounded integers reject JSON booleans in exit codes, sequences and observation counts; malformed evidence blocks rather than being replayed. Verification requires those exact evaluator/input bytes: use the matching checkout for retained development packets, not a newer evaluator silently. This does not alter legacy packet scoring. Development keys are in `evaluator_keys/`, never installed in the adapter home. **This is not enforced hidden-key isolation**: the same OS user can read the repository and parent directories. No OS sandbox, protection against whole-packet rewriting, exhaustive host-effect audit, or production isolation is claimed. The verifier detects inconsistent/missing/stale evidence and unlisted cell artifacts, not arbitrary activity elsewhere on the host. Stronger containment and separately authored held-out fixtures remain prerequisites for consequential evaluation claims.

Optional, provider-free installed-runtime probes use explicit selections:

```bash
HERMES_CANARY_BIN=/absolute/path/to/hermes \
HERMES_CANARY_PYTHON=/absolute/path/to/python \
python3 -m unittest discover -s tests -v
```

A missing default sibling is an unavailable optional probe and skips; an explicitly selected unsupported runtime fails. These variables affect tests only; normal CLI selection uses `--hermes-bin` / `--hermes-python`. The MCP SDK probe actually submits and observes synthetic state over stdio. All configuration writes are in disposable homes.

## Provenance and license

Maintained alongside Herbert. Implementation and publication were materially AI-assisted. Verification claims refer only to recorded executions. MIT licensed; see [LICENSE](LICENSE).
