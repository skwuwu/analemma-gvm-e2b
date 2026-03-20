# Analemma GVM — e2b Demo

Interactive governance demo running inside an [e2b](https://e2b.dev) sandbox.

Pulls the pre-built GVM proxy image from `ghcr.io/skwuwu/analemma-gvm:latest`,
starts the proxy, and runs four governance scenarios in under 60 seconds.

## Scenarios

| Sensitivity | Operation | Expected Decision |
|---|---|---|
| CRITICAL | delete.production_database | 403 Deny (IC-3) |
| PII | read.user_profile | 403 RequireApproval (IC-3) |
| Medium | bulk.export_report ×6 | 429 Throttle (IC-2) |
| Medium | read.document | 200 Allow (IC-1) |

## Quick Start

```bash
pip install -r requirements.txt

# Build the e2b template once (requires e2b CLI)
e2b auth login
e2b template build --name analemma-gvm

# Run the demo
export E2B_API_KEY=your_api_key
python demo.py
```

## Repository Structure

```
.e2b/
  Dockerfile          # e2b template: ghcr.io/skwuwu/analemma-gvm + demo tools
e2b.toml              # template config (1 vCPU, 1GB RAM)
scenarios/
  proxy.toml          # proxy config (no NATS/Redis — standalone WAL only)
  global.toml         # policy: Deny/RequireApproval/Throttle/Allow rules
  secrets.toml        # fake demo credentials
  policies/
    global.toml       # policy file (written by demo.py at runtime)
scripts/
  run_scenario.sh     # manual scenario runner for interactive exploration
demo.py               # main demo script (Python, e2b SDK)
requirements.txt
```

## Core Repository

GVM source: [skwuwu/Analemma-GVM](https://github.com/skwuwu/Analemma-GVM)
Docker image: `ghcr.io/skwuwu/analemma-gvm:latest`
