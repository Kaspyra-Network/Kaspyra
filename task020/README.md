# Task 020 — Intermittent Connectivity (Stage A)

Four real CometBFT v0.38.17 validators with KASPYRA ABCI app in isolated Linux namespaces on a disposable GitHub Actions runner.

Tests complete peer-to-peer blackouts of 15, 30, and 60 seconds, then three 10-second blackout/recovery cycles. Every blackout applies namespace-local unreachable host routes to every other validator. Existing validator processes are not restarted.

Each test waits 5 seconds after isolation before measuring stable block heights to allow in-flight rounds to settle; verifies no height advances during the subsequent timed blackout; restores routes; checks peer reconnection, progress of at least three blocks, and agreement of block/application hashes at a common height.

Caveats: No satellite path is involved. The script does not independently capture packets from already-established TCP sockets, prove Byzantine safety, or evaluate orbital coverage. This stage does not yet test asymmetric links. Failure evidence may be partial if the process exits before the JSON report is written.

Never run the script on a production VPS. The GitHub workflow is the supported environment.
