# Task 008 Phase B — Integration gate

This package is a **pre-integration specification and evidence validator**, not the CometBFT implementation. It deliberately does not modify Phase A code or existing CI. Read `docs/TASK-008B-IMPLEMENTATION.md` and use it to implement the real integration in an environment with access to CometBFT dependencies. `task008b/check_evidence.py` checks only the structure of an evidence report; it cannot verify the report's truth. No live validator network has been run or tested in this package.

Local check: `cd task008b && python -m unittest -v test_check_evidence.py`.
