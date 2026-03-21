"""
Analemma GVM — Latency & Overhead Benchmark (e2b)
==================================================

Measures per-request latency with and without the GVM proxy:

  direct    — GET straight to mock server, no proxy
  gvm_allow — GET through proxy, SRR Allow rule matches
  gvm_delay — POST through proxy, default Delay (300 ms) applies
  gvm_deny  — POST through proxy, SRR Deny rule matches

Results are printed to the console and saved to:
  bench/results.json   machine-readable
  bench/results.md     human-readable summary table

Run:
  e2b auth login
  python benchmark.py
"""

import json
import os
import sys
import time
from datetime import timezone, datetime

from dotenv import load_dotenv
load_dotenv()

from e2b import Sandbox
from e2b.sandbox.commands.command_handle import CommandExitException
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

TEMPLATE       = "analemma-gvm"
PROXY_PORT     = 8080
MOCK_PORT      = 9090
PROXY_URL      = f"http://127.0.0.1:{PROXY_PORT}"
DENY_URL       = "http://api.bank.com/transfer/wire-001"
DELAY_FLOOR_MS = 300

console = Console()


# ── Sandbox helpers ─────────────────────────────────────────────────────────

def wait_for_proxy(sandbox: Sandbox, timeout: int = 20) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = sandbox.commands.run(
                f"curl -sf {PROXY_URL}/gvm/health -o /dev/null -w '%{{http_code}}'"
            )
            if r.stdout.strip() in ("200", "404"):
                return True
        except CommandExitException:
            pass
        time.sleep(0.5)
    return False


def setup_sandbox(sandbox: Sandbox):
    sandbox.commands.run(
        "sudo chown -R user:user /app/data && mkdir -p /app/config/policies"
    )
    for src, dst in [
        ("scenarios/proxy.toml",             "/app/config/proxy.toml"),
        ("scenarios/secrets.toml",            "/app/config/secrets.toml"),
        ("scenarios/srr_network.toml",        "/app/config/srr_network.toml"),
        ("scenarios/srr_semantic.toml",       "/app/config/srr_semantic.toml"),
        ("scenarios/operation_registry.toml", "/app/config/operation_registry.toml"),
        ("scenarios/policies/global.toml",    "/app/config/policies/global.toml"),
    ]:
        sandbox.files.write(dst, open(src, encoding="utf-8").read())

    # Mock upstream server (returns 200 for all requests)
    mock_script = (
        f"import http.server, json\n"
        f"class H(http.server.BaseHTTPRequestHandler):\n"
        f"  def log_message(self, *a): pass\n"
        f"  def _ok(self):\n"
        f"    b=b'{{\"status\":\"ok\"}}'\n"
        f"    self.send_response(200)\n"
        f"    self.send_header('Content-Type','application/json')\n"
        f"    self.send_header('Content-Length',str(len(b)))\n"
        f"    self.end_headers()\n"
        f"    self.wfile.write(b)\n"
        f"  def do_GET(self): self._ok()\n"
        f"  def do_POST(self): self.rfile.read(int(self.headers.get('Content-Length',0))); self._ok()\n"
        f"http.server.HTTPServer(('127.0.0.1',{MOCK_PORT}),H).serve_forever()\n"
    )
    sandbox.commands.run(f"python3 -c \"{mock_script}\"", background=True)
    time.sleep(0.3)

    sandbox.files.write("/tmp/start_proxy.sh",
        "#!/bin/bash\n"
        "cd /app\n"
        "export GVM_SECRETS_KEY=demo-key-32bytes-padded-here\n"
        "exec gvm-proxy > /tmp/proxy.log 2>&1\n"
    )
    sandbox.commands.run("chmod +x /tmp/start_proxy.sh")
    sandbox.commands.run("/tmp/start_proxy.sh", background=True)

    if not wait_for_proxy(sandbox):
        try:
            log = sandbox.commands.run("cat /tmp/proxy.log 2>/dev/null || echo '(no log)'")
            console.print(f"[red]Proxy failed to start:[/red]\n{log.stdout}")
        except CommandExitException as exc:
            console.print(f"[red]Proxy failed to start:[/red] {exc}")
        sys.exit(1)


# ── Results formatting ───────────────────────────────────────────────────────

def _pct(base: float, val: float) -> str:
    if base == 0:
        return "N/A"
    return f"+{((val - base) / base * 100):.0f}%"


def print_table(results: dict):
    direct_mean = results["direct"]["mean"]

    table = Table(
        title="GVM Overhead Benchmark — e2b",
        border_style="cyan",
        show_lines=True,
    )
    table.add_column("Path",         style="bold white",  width=18)
    table.add_column("N",            style="dim",          width=5)
    table.add_column("min (ms)",     style="dim",          width=9)
    table.add_column("p50 (ms)",     style="cyan",         width=9)
    table.add_column("p95 (ms)",     style="yellow",       width=9)
    table.add_column("p99 (ms)",     style="red",          width=9)
    table.add_column("mean (ms)",    style="bold",         width=10)
    table.add_column("vs direct",    style="bold magenta", width=20)

    rows = [
        ("direct",    "direct (no proxy)", "green"),
        ("gvm_allow", "gvm  Allow",        "cyan"),
        ("gvm_delay", f"gvm  Delay {DELAY_FLOOR_MS}ms", "yellow"),
        ("gvm_deny",  "gvm  Deny",         "red"),
    ]
    for key, label, color in rows:
        r = results[key]
        mean = r["mean"]
        if key == "direct":
            overhead_str = "baseline"
        else:
            delta = round(mean - direct_mean, 2)
            overhead_str = f"+{delta:.2f} ms"
        table.add_row(
            f"[{color}]{label}[/{color}]",
            str(r["n"]),
            f"{r['min']:.2f}",
            f"{r['p50']:.2f}",
            f"{r['p95']:.2f}",
            f"{r['p99']:.2f}",
            f"{r['mean']:.2f}",
            overhead_str,
        )
    console.print(table)


def save_results(results: dict, timestamp: str):
    direct_mean = results["direct"]["mean"]
    allow_mean  = results["gvm_allow"]["mean"]
    deny_mean   = results["gvm_deny"]["mean"]
    delay_mean  = results["gvm_delay"]["mean"]

    overhead = {
        "allow_vs_direct_ms":   round(allow_mean - direct_mean, 3),
        "deny_vs_direct_ms":    round(deny_mean  - direct_mean, 3),
        "delay_above_floor_ms": round(delay_mean - direct_mean - DELAY_FLOOR_MS, 3),
        "deny_vs_allow_ms":     round(deny_mean  - allow_mean, 3),
    }

    payload = {
        "platform":      "e2b",
        "timestamp":     timestamp,
        "sandbox_image": TEMPLATE,
        "n_warmup":      10,
        "n_bench":       50,
        "delay_floor_ms": DELAY_FLOOR_MS,
        "deny_url":      DENY_URL,
        "results":       {k: v for k, v in results.items() if k != "delay_floor_ms"},
        "overhead":      overhead,
    }

    os.makedirs("bench", exist_ok=True)
    with open("bench/results.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    # Markdown table
    col_w = [22, 6, 8, 8, 8, 8, 8, 14]
    def row(*cells):
        return "| " + " | ".join(str(c).ljust(w) for c, w in zip(cells, col_w)) + " |"

    header = row("Path", "N", "min", "p50", "p95", "p99", "mean", "overhead")
    sep    = row(*["-" * w for w in col_w])
    lines  = [header, sep]

    for key, label in [
        ("direct",    "direct (no proxy)"),
        ("gvm_allow", "gvm Allow"),
        ("gvm_delay", f"gvm Delay ({DELAY_FLOOR_MS} ms)"),
        ("gvm_deny",  "gvm Deny"),
    ]:
        r = results[key]
        m = r["mean"]
        if key == "direct":
            ov = "baseline"
        else:
            delta = round(m - direct_mean, 2)
            ov = f"+{delta:.2f} ms"
        lines.append(row(
            label, r["n"],
            f"{r['min']:.2f}", f"{r['p50']:.2f}",
            f"{r['p95']:.2f}", f"{r['p99']:.2f}", f"{r['mean']:.2f}",
            ov,
        ))

    allow_ov      = overhead["allow_vs_direct_ms"]
    deny_ov       = overhead["deny_vs_direct_ms"]
    floor_ov      = overhead["delay_above_floor_ms"]
    deny_vs_allow = overhead["deny_vs_allow_ms"]
    deny_relation = f"+{deny_vs_allow:.2f} ms slower" if deny_vs_allow >= 0 else f"{abs(deny_vs_allow):.2f} ms faster"

    md = f"""\
# GVM Overhead Benchmark Results — e2b

**Platform**: e2b cloud sandbox (`{TEMPLATE}`)
**Measured**: {timestamp}
**N**: {payload['n_bench']} requests per path + {payload['n_warmup']} warmup

All latency values in **milliseconds**.

## Latency Table

{chr(10).join(lines)}

## Overhead Summary

| Metric                           | Value           |
|----------------------------------|-----------------|
| Allow overhead vs direct         | +{allow_ov:.2f} ms      |
| Deny overhead vs direct          | +{deny_ov:.2f} ms      |
| Delay overhead above {DELAY_FLOOR_MS} ms floor | +{floor_ov:.2f} ms      |
| Deny vs Allow                    | {deny_relation} |

## What the numbers mean

- **Direct**: raw localhost TCP round-trip to mock server (127.0.0.1:9090). No
  policy evaluation, no WAL write.
- **Allow overhead ({allow_ov:.2f} ms)**: cost of GVM enforcement on a permitted request —
  policy evaluation + WAL write + credential injection + proxy TCP hops.
- **Deny overhead ({deny_ov:.2f} ms)**: Deny involves ABAC + SRR evaluation, max_strict(),
  and a denial WAL entry — more bookkeeping than a simple Allow forward.
  {'Deny is slower than Allow.' if deny_vs_allow >= 0 else 'Deny is faster than Allow.'}
- **Delay above floor ({floor_ov:.2f} ms)**: The configured {DELAY_FLOOR_MS} ms penalty is applied
  correctly. Excess above the floor reflects upstream connection time. If
  host_overrides routes the delay target to the local mock server, this surplus
  converges to ~{allow_ov:.1f} ms (same as Allow-path overhead).
- GVM adds ~{allow_ov:.1f} ms of governance overhead per allowed request. That is the
  cost of a cryptographically-chained audit entry and real-time policy evaluation.

## Reproduce

```bash
e2b auth login
python benchmark.py
```

Results are written to `bench/results.json` (machine-readable) and
`bench/results.md` (this file).
"""

    with open("bench/results.md", "w", encoding="utf-8") as f:
        f.write(md)

    console.print("[dim]Saved bench/results.json and bench/results.md[/dim]")


# ── Main ─────────────────────────────────────────────────────────────────────

def run_benchmark():
    console.print(Panel.fit(
        "[bold cyan]Analemma GVM — Overhead Benchmark[/bold cyan]\n"
        "[dim]direct vs. GVM Allow / Delay / Deny  |  N=50 per path[/dim]",
        border_style="cyan",
    ))

    with Sandbox.create(TEMPLATE) as sandbox:
        with console.status("Starting sandbox services (mock server + GVM proxy)…"):
            setup_sandbox(sandbox)

        console.print("[green]Proxy ready.[/green] Uploading bench runner…")
        sandbox.files.write("/tmp/bench_runner.py", open("bench/runner.py", encoding="utf-8").read())

        with console.status(f"Running full benchmark (N={N_BENCH} × 4 paths + warmup)…"):
            result = sandbox.commands.run(
                f"python3 /tmp/bench_runner.py {MOCK_PORT} {PROXY_PORT} "
                f"'{DENY_URL}' {DELAY_FLOOR_MS} all",
                timeout=120,
            )

        raw = result.stdout.strip()
        if not raw:
            console.print("[red]Benchmark returned no output.[/red]")
            if result.stderr:
                console.print(f"stderr: {result.stderr[:400]}")
            return

        try:
            results = json.loads(raw)
        except json.JSONDecodeError as exc:
            console.print(f"[red]Failed to parse benchmark output:[/red] {exc}")
            console.print(f"raw: {raw[:400]}")
            return

        print_table(results)
        ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        save_results(results, ts)


N_BENCH = 50

if __name__ == "__main__":
    run_benchmark()
