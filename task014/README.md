# KASPYRA Task 014 — Satellite-like validator network stress

This is a **local TCP impairment experiment**, not satellite hardware or a verified satellite-only path. Reuses the proven Task 013B four-validator CometBFT harness without modifying consensus.

## Scenarios

- 500 ms per received TCP chunk (not calibrated RTT)
- 1000 ms per received TCP chunk
- 100–700 ms randomized per chunk jitter (deterministic seed)
- 128 kB/s per proxied stream approximate bandwidth shaping
- 1% probability of connection disruption per chunk (not IP packet loss)
- Verified 2-vs-2 partition and convergence after restoration

These scenarios are run sequentially. Each measures height, duration and bytes. STALL is a measured outcome rather than a false PASS; subsequent recovery must succeed or the job fails. `task014-result.json` is uploaded as a GitHub artifact even on failure.

**Limitations:** Chunk-based sleeps are not a calibrated network emulator. Bandwidth is per stream and approximate. The 1% scenario closes TCP connections, not packet dropping. Proxy and consensus behavior are not evidence of production security, space-only routing or reliable satellite service. Future work requires controlled netem and real provider tests.

Upload `task014/` to repo root and `task014-satellite-stress.yml` separately to `.github/workflows/`. Do not upload the visible root workflow into the repository root.
