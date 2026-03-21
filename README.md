# Analemma GVM — e2b Demo

Five governance scenarios running inside an [e2b](https://e2b.dev) cloud sandbox.
GVM proxy starts inside the sandbox, runs enforcement, writes an immutable WAL.

## Demo

<!-- Replace yCyzeUxtuWYLtwGE with the actual recording ID after upload -->
[![asciicast](https://asciinema.org/a/yCyzeUxtuWYLtwGE.svg)](https://asciinema.org/a/yCyzeUxtuWYLtwGE)

> Recorded on a live e2b cloud sandbox using the maintainer's personal API key and account.
> No mock — the proxy, WAL, and policy engine are all running in-sandbox.

## What you'll see

| Scenario | Agent action | GVM decision |
|----------|-------------|--------------|
| 1. API key isolation | Agent env has no key — proxy injects post-enforcement | Agent uses the key, but can never read it |
| 2. Graduated enforcement | Same domain, different method+path → different decision | Allow → Delay → Deny |
| 3. Merkle audit | WAL tamper attempt | Integrity check fails with proof |
| 4. Forgery detection | `gvm.read` declared, `POST /transfer` sent | Cross-layer forgery → Deny |
| 5. Auto-rollback | `auto_checkpoint` + forced Deny mid-sequence | `GVMRollbackError` triggered, state restored |

## Quick Start

```bash
e2b auth login
pip install -r requirements.txt
python demo.py
```

Total time: ~2 minutes.

## Overhead Benchmark

Measures GVM proxy latency vs. direct HTTP (N=50 per path, 10 warmup):

| Path               |  p50 (ms) |  p99 (ms) | mean (ms) | vs direct    |
|--------------------|-----------|-----------|-----------|--------------|
| direct (no proxy)  |      0.22 |      0.29 |      0.23 | baseline     |
| gvm Allow          |      0.51 |      0.61 |      0.51 | +0.28 ms     |
| gvm Delay (300 ms) |    310.41 |    314.24 |    310.37 | +310.14 ms * |
| gvm Deny           |      3.96 |      4.18 |      3.92 | +3.69 ms     |

GVM enforcement overhead per request: **~0.28 ms** (policy evaluation + WAL write + credential injection).

\* Delay measured at 310 ms for a 300 ms configured floor: the excess ~10 ms is WAL write overhead + timer jitter. With host_overrides correctly routing the delay target to the local mock server, the floor is hit precisely.

Full results: [`bench/results.md`](bench/results.md) · [`bench/results.json`](bench/results.json)

```bash
e2b auth login
python benchmark.py
```

### Why Deny is slower than Allow

Allow returns a 200 immediately and writes the WAL entry in the background. Deny **blocks until
the WAL entry is durably flushed to disk** before returning the 403 — that fsync is the source
of the extra latency.

This is a deliberate design choice. Cilium and Envoy use best-effort, fire-and-forget logging:
drop the packet (or pass it), emit a log event asynchronously, move on. That trade-off is
reasonable for network traffic — losing a flow log is operationally annoying but rarely
consequential.

AI agent actions are a different category. A wire transfer, a credential read, a file deletion —
these are high-stakes, often irreversible operations. If the denial record is lost before it
reaches durable storage, the audit chain breaks: a security review cannot confirm the action
was blocked, a compliance audit cannot verify the policy was enforced, and tamper detection
loses its anchor point. The cost of that loss far exceeds the ~3.7 ms of added latency on the
rejection path.

## No LLM required — what is mocked and why

This demo shows GVM's governance layer in isolation. LLM inference is not the subject being tested.

| What looks like an agent | What actually runs |
|--------------------------|-------------------|
| `FinanceAgent.read_data()` | `requests.get()` to a local Python mock server on port 9090 |
| `FinanceAgent.send_report()` | `requests.post()` to the same mock server |
| `FinanceAgent.wire_transfer()` | `requests.post()` — intercepted and Denied by GVM before reaching mock |
| `analyze()` (step 2) | Hardcoded print — simulates LLM reasoning step |
| Token cost numbers | Hardcoded constants in `TOKEN_COSTS` dict — representative, not measured |
| `GVMRollbackError` in scenario 5 | Real exception raised by the GVM SDK when proxy returns 403 + rollback signal |

**The mock server** (`http.server.HTTPServer` on port 9090) mimics an upstream API:
it returns `{"status": "ok"}` for every request, and echoes the `Authorization` header
for scenario 1. It has no business logic — it exists only to give the proxy a real TCP
connection to enforce against.

**What is real:**
- GVM proxy binary enforcing actual HTTP requests
- SRR rules matching on method + path
- WAL entries written with SHA-256 event hashes
- Merkle chain over those hashes (tamper detection in scenario 3)
- `@ic()` decorator injecting governance headers onto real `requests.Session` calls
- `GVMDeniedError` / `GVMRollbackError` raised from real proxy 403 responses

## First-time setup (one-time only)

The demo uses a pre-built e2b template (`p8db70me9zsdy33gvyyr`). To rebuild it under your own account:

```bash
npm install -g @e2b/cli
e2b auth login
e2b template create analemma-gvm --dockerfile .e2b/Dockerfile --cpu-count 2 --memory-mb 1024
```

This pulls `ghcr.io/skwuwu/analemma-gvm:latest` and registers the template under your account (~50 seconds).
Update `e2b.toml` with the new `template_id`, then `python demo.py` works without rebuilding.

## Repository layout

```
.e2b/
  Dockerfile          # e2b template: analemma-gvm image + Python demo deps
e2b.toml              # template config (1 vCPU, 1 GB RAM)
scenarios/
  proxy.toml          # proxy config (standalone WAL, no external deps)
  srr_network.toml    # SRR network rules
  secrets.toml        # demo credentials (fake — held by proxy, not agent)
  policies/
    global.toml       # ABAC policy
demo.py               # main demo (Python, e2b SDK + gvm SDK)
benchmark.py          # overhead benchmark: direct vs GVM Allow/Delay/Deny
bench/
  runner.py           # benchmark script uploaded and run inside the sandbox
  results.json        # last run results (machine-readable)
  results.md          # last run results (human-readable table)
requirements.txt
```

## Core repository

Source and docs: [skwuwu/Analemma-GVM](https://github.com/skwuwu/Analemma-GVM)
Docker image: `ghcr.io/skwuwu/analemma-gvm:latest`
