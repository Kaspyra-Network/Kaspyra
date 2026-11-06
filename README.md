# KASPYRA

**Built for Earth. Designed for distance.**

KASPYRA is an **early-stage, open-source research project** investigating how cryptographically verifiable transaction infrastructure can remain useful when terrestrial connectivity is unreliable, intermittent, or unavailable. Its immediate focus is Earth-based networks; asynchronous Earth–Mars settlement is a long-term research question, not an available capability.

> **Status (November 2026):** Research and local simulation only. No production blockchain, satellite deployment, hardware wallet, token, partnership, or verified satellite test exists.

## Research thesis

Can store-and-forward, authenticated relays and explicit finality-state reporting make blockchain transactions more usable across delayed, disrupted, and hybrid terrestrial/satellite links **without weakening consensus safety**?

We are comparing three options rather than assuming a new Layer 1 is required:

1. **Transport overlay for existing blockchains** — resilient forwarding and synchronization without changing consensus.
2. **Specialized settlement integration** — adapt an existing settlement stack to intermittent connectivity.
3. **Purpose-built network** — only if controlled evidence establishes a material advantage that justifies its security and operating costs.

Starlink and other satellite providers are **possible communications transports via authorized ground terminals**, not partners or hosting environments for our validators.

## Explore

- [Whitepaper (research draft)](WHITEPAPER.md)
- [Architecture and alternatives](ARCHITECTURE.md)
- [Research questions and evidence rules](RESEARCH.md)
- [Roadmap](ROADMAP.md)
- [Local disruption simulator](experiments/README.md)
- [Security policy](SECURITY.md) · [Contributing](CONTRIBUTING.md)

## First reproducible experiment

Requires Python 3.10+ and no external dependencies:

```sh
python3 -m unittest discover -s experiments -p 'test_*.py' -v
python3 experiments/disruption_sim.py --seed 42 --trials 200
```

The experiment models **message delivery only**; it does not implement a blockchain, transaction validation, consensus, or finality. Its scenarios are synthetic, not measurements of Starlink or other networks.

## Open research and provenance

We distinguish **observed test results**, **published external evidence**, **assumptions**, and **aspirations**. See [research references](docs/references/README.md). Contributions are welcome via issues and pull requests.

**License:** Source code in this repository is offered under Apache-2.0 (see LICENSE). Brand names, marks and logos are not granted trademark rights by that license. Documentation and imagery licensing should be confirmed before redistribution beyond the repository's code license.
