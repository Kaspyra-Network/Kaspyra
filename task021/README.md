# KASPYRA Task 021A — Consensus bandwidth benchmark

This isolated GitHub Actions experiment starts four real CometBFT v0.38.17 validators and the KASPYRA ABCI application in network namespaces. It measures validator-facing interface RX/TX byte counters over 30-second empty-block windows (baseline and 300 ms emulated RTT), plus aggregate traffic during a 15-second blackout and recovery.

**Not a satellite test.** No actual satellite transport, transaction traffic, peak bandwidth, or provider suitability is established. Per-block figures are *average interface traffic divided by blocks*, not incremental consensus message cost. Outage/recovery byte totals include both periods. All traffic shaping and namespaces are confined to disposable CI. Never run `bandwidth.py` on the production VPS.

Expected evidence: `task021-bandwidth-evidence.json`, with `satellite_verified: false`. Review numerical measurements before selecting any satellite provider. Follow-up tests should add transactions, shorter sampling windows for peaks, and protocol-level attribution.
