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
- dependency-free event indexing helpers
- vendorable stdlib-only reference code

Projects such as the om.pub RSO Archive define their own `docChainId` profile:

- what `contentHash` means
- how docs are canonicalized
- how parentage is validated
- which attestations are eligible
- how competing branches are scored

The current RSO v1 profile is:

```text
profileURI = https://om.pub/rso/doc-chain/v1
docChainId = keccak256(profileURI)
           = 0x8621c2851714436d60da45cf0e11253114a4f2002f73ddc159b4dc88fea5611d
```

Doc Chain does **not** define one universal consensus mechanism. It
publishes signed, timestamped claims. Each doc chain supplies its own
validation and canonicality rules.

Start with [docs/protocol.md](docs/protocol.md) for the contract boundary,
typed-data model, event semantics, and profile responsibilities.

Ethereum build, test, deployment, and audit notes live in
[docs/ethereum.md](docs/ethereum.md), [docs/audit.md](docs/audit.md),
[docs/threat-model.md](docs/threat-model.md), and
[docs/release-checklist.md](docs/release-checklist.md).

Security feedback is welcome. See [SECURITY.md](SECURITY.md) for responsible
disclosure guidance. This is not currently a formal bug bounty.

## Repository Layout

```text
abi/                committed contract ABI
contracts/          Ethereum contract source
deployments/        deployed address registry
docs/               protocol and integration docs
fixtures/           deterministic EIP-712 fixtures
reference/          stdlib-only event models and ABI constants
scripts/            stdlib-only project maintenance scripts
tests/              stdlib unit tests for reference helpers
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
    address onBehalfOf;
    DocBlock docBlock;
    string uri;
    uint256 deadline;
}
```

For each attestation, the contract emits the `hashStruct(DocBlock)` value as
`blockHash`. Because `parentHash` is part of the hashed block, changing any
historical block changes every descendant block hash. `docRef` is the
profile-defined reference used for grouping, browsing, and querying blocks;
`blockHash` is identity and `parentHash` is ancestry.

`onBehalfOf` is optional signed metadata for profiles that support delegated
identity. Use `address(0)` when the attestation is only from the signing key.

`uri` is optional signed metadata for profile-defined location claims. It can be
empty, a direct fetch URI, or a profile-defined `data:` URI containing bounded
locator metadata. The contract stores and emits it but does not interpret it.

## Reuse Model

Production projects should vendor the small `reference/docchain` module into
their own repository instead of installing it at runtime. This keeps operators
dependency-free and reviewable.

```text
vendor/docchain/
  VERSION
  abi.py
  indexer.py
  logs.py
  model.py
  store.py
```

Profile-specific code lives in the consuming project.

The reusable indexer layer includes provider backoff, provider block-range
limit handling, checkpoint/resume, append-only event caches, and generic static
index generation. Consuming projects should usually wrap that layer with only
network/profile constants and project-specific presentation fields.

The decoder accepts the current `DocAttested` event shape and the original
event shape without `onBehalfOf`; legacy events are normalized with
`onBehalfOf` set to `address(0)`.

## Event Indexing

`scripts/index_events.py` can scan a deployed `DocChain` contract with raw
Ethereum JSON-RPC and emit neutral `DocAttested` records:

```bash
python3 scripts/index_events.py \
  --rpc-url https://... \
  --address 0x... \
  --from-block 123456 \
  --format jsonl
```

To quickly see which Ethereum blocks contain attestations:

```bash
python3 scripts/index_events.py \
  --rpc-url https://... \
  --address 0x... \
  --from-block 123456 \
  --format blocks
```

## Attestation Scripts

The operator flow is split into explicit steps:

```bash
make prepare-attestation PREPARE_ATTESTATION_ARGS="\
--deployment deployments/sepolia.json \
--doc-chain-id 0x... \
--doc-ref 20260514000000 \
--content-hash 0x... \
--uri ar://..."

make sign-attestation
make submit-attestation SUBMIT_ATTESTATION_ARGS="--dry-run"
make submit-attestation
```

Preparation is stdlib-only Python. Signing and submission use Foundry `cast` so
the repo does not carry local Keccak-256 or secp256k1 implementations.
