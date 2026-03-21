# GVM Overhead Benchmark Results — e2b

**Platform**: e2b cloud sandbox (`analemma-gvm`)
**Measured**: 2026-03-21T04:10:49Z
**N**: 50 requests per path + 10 warmup

All latency values in **milliseconds**.

## Latency Table

| Path                   | N      | min      | p50      | p95      | p99      | mean     | overhead       |
| ---------------------- | ------ | -------- | -------- | -------- | -------- | -------- | -------------- |
| direct (no proxy)      | 50     | 0.21     | 0.22     | 0.28     | 0.29     | 0.23     | baseline       |
| gvm Allow              | 50     | 0.42     | 0.51     | 0.58     | 0.61     | 0.51     | +0.28 ms       |
| gvm Delay (300 ms)     | 50     | 308.50   | 310.41   | 311.27   | 314.24   | 310.37   | +310.14 ms     |
| gvm Deny               | 50     | 2.91     | 3.96     | 4.12     | 4.18     | 3.92     | +3.69 ms       |

## Overhead Summary

| Metric                           | Value           |
|----------------------------------|-----------------|
| Allow overhead vs direct         | +0.28 ms      |
| Deny overhead vs direct          | +3.69 ms      |
| Delay overhead above 300 ms floor | +10.14 ms      |
| Deny vs Allow                    | +3.41 ms slower |

## What the numbers mean

- **Direct**: raw localhost TCP round-trip to mock server (127.0.0.1:9090). No
  policy evaluation, no WAL write.
- **Allow overhead (0.28 ms)**: cost of GVM enforcement on a permitted request —
  policy evaluation + WAL write + credential injection + proxy TCP hops.
- **Deny overhead (3.69 ms)**: Deny involves ABAC + SRR evaluation, max_strict(),
  and a denial WAL entry — more bookkeeping than a simple Allow forward.
  Deny is slower than Allow.
- **Delay above floor (10.14 ms)**: The configured 300 ms penalty is applied
  correctly. Excess above the floor reflects upstream connection time. If
  host_overrides routes the delay target to the local mock server, this surplus
  converges to ~0.3 ms (same as Allow-path overhead).
- GVM adds ~0.3 ms of governance overhead per allowed request. That is the
  cost of a cryptographically-chained audit entry and real-time policy evaluation.

## Reproduce

```bash
e2b auth login
python benchmark.py
```

Results are written to `bench/results.json` (machine-readable) and
`bench/results.md` (this file).
