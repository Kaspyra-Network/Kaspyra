# KASPYRA Task 009 — Phase A

This package **adds** real CometBFT validator-process failure tests without changing Task 008C or Task 008D.

## Covered

- Four-validator healthy baseline, comparing canonical block IDs and application hashes at the same height.
- Stop one validator: verify three remaining validators advance at least three blocks, restart the fourth, and verify convergence.
- Stop two validators: verify two surviving processes remain healthy and their heights do not advance over a 15-second observation interval (after a 4-second settle interval).
- Restart both stopped validators: verify finalization resumes and all four agree on a canonical block and application hash.

## Not yet covered

- **True 2–2 network partition** with four live processes: NOT IMPLEMENTED. Requires P2P isolation and independent proof that the isolation took effect.
- **ABCI application process restart**: NOT IMPLEMENTED.
- Byzantine attacks, satellite links, security proof, production deployment: NOT TESTED.

The workflow should only be described as **Task 009 Phase A PASS** if the actual dedicated job succeeds and prints `PASS_PHASE_A_ONLY`. It must not be called a full Task 009 pass.

## Install

Upload this ZIP's contents at the repository root, retaining `.github/workflows/task009-network.yml` and `task009/run_faults.py`. Do not overwrite any existing files.

## Technical caveats

This test reuses the Task 008D Go module, CometBFT 0.38.17 and CI dependency resolution. A 15-second absence of progress is an empirical smoke test, not a proof of safety. The test currently writes a structured result to `task009-result.json` only on success. CI has not yet been run on this package; investigate failures rather than weakening assertions.
