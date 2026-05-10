# Doc Chain Attestation Protocol

![Doc Chain Attestation](assets/2026-05-05-doc-chain-attestation.png)

A generic Ethereum witness protocol for attestation-driven doc chains.

Doc Chain provides the reusable rail:

- a minimal append-only Ethereum contract
- a `DocBlock` model with parent-hash linkage
- EIP-712 typed attestations
- EOA and EIP-1271 signature support
- contract-level deadlines and duplicate prevention
- neutral event model helpers
- vendorable stdlib-only reference code

Projects such as the om.pub RSO Archive define their own `docChainId` profile:

- what `contentHash` means
- how docs are canonicalized
- how parentage is validated
- which attestations are eligible
- how competing branches are scored

Doc Chain does **not** define one universal consensus mechanism. It
publishes signed, timestamped claims. Each doc chain supplies its own
validation and canonicality rules.

Start with [docs/protocol.md](docs/protocol.md) for the contract boundary,
typed-data model, event semantics, and profile responsibilities.

Ethereum build, test, deployment, and audit notes live in
[docs/ethereum.md](docs/ethereum.md), [docs/audit.md](docs/audit.md),
[docs/threat-model.md](docs/threat-model.md), and
[docs/release-checklist.md](docs/release-checklist.md).

## Repository Layout

```text
abi/                committed contract ABI
contracts/          Ethereum contract source
deployments/        deployed address registry
docs/               protocol and integration docs
fixtures/           deterministic EIP-712 fixtures
reference/          stdlib-only event models and ABI constants
scripts/            stdlib-only project maintenance scripts
```

## Core Model

```solidity
struct DocBlock {
    bytes32 docChainId;
    uint64 docRef;
    bytes32 parentHash;
    bytes32 contentHash;
}

struct DocAttestation {
    address attester;
    DocBlock docBlock;
    string uri;
    uint256 deadline;
}
```

The contract computes `blockHash` from `DocBlock`. Because `parentHash` is part
of the hashed block, changing any historical block changes every descendant
block hash. `docRef` is the profile-defined reference used for grouping,
browsing, and querying blocks; `blockHash` is identity and `parentHash` is
ancestry.

## Reuse Model

Production projects should vendor the small `reference/docchain` module into
their own repository instead of installing it at runtime. This keeps operators
dependency-free and reviewable.

```text
vendor/docchain/
  VERSION
  abi.py
  model.py
```

Profile-specific code lives in the consuming project.
