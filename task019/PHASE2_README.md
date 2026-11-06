# Task 019 Phase 2 — real validators under isolated NetEm

This experimental harness starts four real CometBFT v0.38.17 nodes and the existing KASPYRA Task 008C ABCI application, one per Linux network namespace. A private Linux bridge connects four virtual Ethernet pairs. Each interface receives a NetEm qdisc; the harness verifies its configuration and measures RTT between validator namespaces. It tests baseline, three RTT targets, jitter/loss, a two-versus-two network partition, and recovery. Consensus agreement is checked using matching block and application hashes.

**Run only on a disposable Linux runner.** It requires root privileges and temporarily creates network namespaces, virtual interfaces, and qdiscs. It does not touch host physical interfaces, Docker, UFW, or production services. GitHub Actions is the intended environment. Never run it on the shared production VPS.

The 1% loss is configured **per egress interface**, not end-to-end. RTT values are experimental parameters, not satellite measurements. A `STALL` outcome is preserved in the JSON evidence; a passing run with stalls is not a claim of liveness in every scenario. Tests do not establish Byzantine safety, satellite transport, satellite-only routing, orbital availability, or production readiness.

Evidence: `task019-validator-evidence.json`, uploaded even on failure. The harness has been syntax-checked but has **not yet been executed** with CometBFT or Linux network namespaces; the first CI run is validation, not a guaranteed pass.
