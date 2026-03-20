# Analemma GVM — e2b Demo

Five governance scenarios running inside an [e2b](https://e2b.dev) cloud sandbox.
GVM proxy starts inside the sandbox, runs enforcement, writes an immutable WAL.

## What you'll see

| Scenario | Agent action | GVM decision |
|----------|-------------|--------------|
| 1. API key theft | Reads `STRIPE_KEY` from env | Deny — key never reaches agent |
| 2. Graduated enforcement | Sensitivity escalation across 3 ops | Allow → Delay → Deny |
| 3. Merkle audit | WAL tamper attempt | Integrity check fails with proof |
| 4. Forgery detection | `gvm.read` declared, `POST /transfer` sent | Cross-layer forgery → Deny |
| 5. Auto-rollback | `auto_checkpoint` + forced Deny mid-sequence | `GVMRollbackError` triggered, state restored |

## Quick Start

```bash
export E2B_API_KEY=your_api_key_here
pip install -r requirements.txt
python demo.py
```

Total time: ~2 minutes.

Get an API key at [e2b.dev/dashboard](https://e2b.dev/dashboard).

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
  global.toml         # ABAC policy: Deny/RequireApproval/Throttle/Allow
  srr_network.toml    # SRR network rules
  secrets.toml        # demo credentials (fake — held by proxy, not agent)
  policies/
    global.toml       # policy file (written by demo.py at runtime)
demo.py               # main demo (Python, e2b SDK + gvm SDK)
requirements.txt
```

## Core repository

Source and docs: [skwuwu/Analemma-GVM](https://github.com/skwuwu/Analemma-GVM)
Docker image: `ghcr.io/skwuwu/analemma-gvm:latest`
