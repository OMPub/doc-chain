# Document Chain Protocol

Document Chain is a generic witness log for document chains. It gives projects
a common way to publish signed claims about hash-linked documents while leaving
validation and consensus rules to each `docChainId` profile.

## Contract Boundary

It does:

- verify EIP-712 signatures
- support EOAs and EIP-1271 contract wallets
- enforce signature deadlines
- enforce duplicate prevention
- compute and emit `blockHash` and `uriHash`
- emit append-only events
- expose enough event data for off-chain indexers and viewers

Document Chain is not a full blockchain consensus protocol.

It does not:

- choose the canonical branch
- validate external document bytes onchain
- fetch from storage networks
- define a universal reputation or voting system
- know about any specific NFT collection or community metric
- sponsor gas or define relayer eligibility

The contract is intentionally just the raw witness log. Clients, relayers,
indexers, viewers, and operator tooling apply profile rules for the attested
`docChainId`.

Onchain validation is deliberately out of scope. Smart contracts cannot fetch
from Arweave, IPFS, HTTPS, or project APIs, and an oracle would reintroduce the
centralized trust this protocol is meant to avoid. The contract records signed
claims; profile-aware clients decide whether those claims are valid and how
much weight they carry.

## Domain Separator

The EIP-712 domain separator must include `chainId` and `verifyingContract` so
signatures cannot be replayed across chains or contract deployments:

```solidity
struct EIP712Domain {
    string name;               // "Document Chain"
    string version;            // e.g. "1"
    uint256 chainId;           // Ethereum chain id
    address verifyingContract; // deployed Document Chain contract
}
```

The `version` field gives the protocol a clean way to deploy a future
attestation shape without ambiguous signatures.

## DocBlock

```solidity
struct DocBlock {
    bytes32 docChainId;
    uint64 docRef;
    bytes32 parentHash;
    bytes32 contentHash;
}
```

Field meanings:

- `docChainId`: profile identifier, conventionally the hash of a profile URI,
  for example `keccak256("https://om.pub/rso/docchain/v1")`
- `docRef`: profile-defined unsigned 64-bit reference for grouping, browsing,
  and querying blocks within a `docChainId`
- `parentHash`: previous `DocBlock` hash, or `bytes32(0)` for genesis
- `contentHash`: profile-defined digest of the document payload

The contract computes:

```text
blockHash = hashStruct(DocBlock)
```

Because `parentHash` is inside the block being hashed, any change to a middle
block changes that block hash and every descendant hash. This is the protocol's
document-chain linkage.

`docRef` is not the block identity and does not establish ancestry. Block
identity is `blockHash`; ancestry is `parentHash`. The `docRef` lets a profile
define how humans and indexers refer to a block, such as a timestamp, sequence
number, round, edition, checkpoint, generation, or packed coordinate. Profile
indexers can decode `docRef` into richer labels such as dates, names, or paths.

## Attestation

```solidity
struct DocumentAttestation {
    address attester;
    DocBlock docBlock;
    string uri;
    uint256 deadline;
}
```

`attester` is the wallet making the claim. It is part of the signed payload so
EOAs and EIP-1271 contract wallets can both be supported.

`uri` is optional. Empty URI attestations are hash-only chain attestations. A
non-empty URI additionally claims that the location resolves to bytes matching
the profile rules for `contentHash`.

`uriHash` is deliberately not part of the signed struct. The contract computes
`keccak256(bytes(uri))` after enforcing the URI size cap, uses that computed
value for duplicate prevention, and emits it in `DocumentAttested`.

The contract must reject any attestation where `bytes(uri).length > 8192`.
That 8 KiB cap keeps event payloads and downstream indexes bounded while still
leaving room for long signed URLs, parameterized rendering URLs, and
self-contained URI schemes. Profiles and relayers may enforce lower caps for
sponsored submissions or profile-specific URI types.

## Signature Verification

Anyone can submit a signed attestation onchain: the signer, a relayer, a
GitHub Action, another operator, or a future archival service. The contract
verifies that the signature is valid for the named `attester` and records that
address as the attester. `msg.sender` is only the gas payer/courier.

The verifier must branch by attester type:

- If `attester` has no code, recover the EOA signer from the EIP-712 digest and
  require it to equal `attester`.
- If `attester` has code, call `isValidSignature(digest, signature)` and
  require the EIP-1271 magic value.

This avoids trying to recover a signer from a contract-wallet signature, which
is not how EIP-1271 works.

## Deadline Enforcement

The contract must reject any attestation whose `deadline` has passed:

```text
revert if block.timestamp > deadline
```

Relayers should apply the same check before paying gas, and should reject
signatures that are too close to expiry to survive normal transaction inclusion.
Applications should set deadlines long enough to survive a normal relayer queue
and short enough that a stale or compromised signature is not reusable days
later.

## Duplicate Rule

Contract-level uniqueness:

```text
attested[attester][docChainId][docRef][parentHash][contentHash][uriHash] = true
```

Implementation can store a packed key:

```solidity
bytes32 key = keccak256(
    abi.encode(
        attester,
        docBlock.docChainId,
        docBlock.docRef,
        docBlock.parentHash,
        docBlock.contentHash,
        uriHash
    )
);
```

This lets a signer attest distinct publications for the same document block,
such as Arweave and IPFS copies, while blocking repeated attestations to the
same publication claim.

## Event

The contract must emit an append-only event for every successful attestation:

```solidity
event DocumentAttested(
    bytes32 indexed docChainId,
    address indexed attester,
    uint64 indexed docRef,
    address submitter,
    bytes32 parentHash,
    bytes32 blockHash,
    bytes32 contentHash,
    bytes32 uriHash,
    string uri
);
```

`submitter` is `msg.sender`: the gas payer/courier. It is not part of
attestation validity.

The event must be sufficient for indexers and viewers to reconstruct witness
history without heavy contract read APIs. From events alone, an indexer can
reconstruct:

- every document chain that has attestations
- every document reference that has attestations
- every attester for each document reference
- who paid gas for each submission
- every candidate `blockHash` for a document reference
- the `parentHash` each candidate claims to extend
- each `contentHash` and URI attested for that candidate
- hash-only attestations where `uri == ""`
- duplicate-prevention identity by recomputing the attestation key
- fork/dispute state by grouping multiple block candidates for a document
  reference

A neutral read model can be generated purely from logs:

```text
docChainId
  docRef
    blockHash
      parentHash
      contentHash
      attestors[]
      submitters[]
      locations[uriHash]
        uri
        attestors[]
```

The contract does not need large paginated reference reads for normal rendering.
Projects can publish compact JSON indexes from events and use targeted RPC
calls when a viewer wants proof for a specific event or document reference.

## Profiles

Each `docChainId` defines a profile outside the contract:

- document canonicalization
- content hash algorithm
- `docRef` meaning and decoding
- genesis rule
- URI validation
- eligible attesters
- branch scoring and canonicality
- relayer sponsorship policy, if any

The recommended convention is:

```text
docChainId = keccak256(profileURI)
```

where `profileURI` points to human-readable profile documentation, for example:

```text
https://om.pub/rso/docchain/v1
```

That URI can describe the document canonicalization rules, `docRef` decoding,
URI interpretation, eligible attesters, and branch scoring for the profile.
`bytes32` is sufficient because `keccak256` produces a 32-byte identifier. The
profile URI is not recoverable from `docChainId`; projects must distribute the
URI through docs, indexer config, relayer config, viewer config, or other
offchain profile metadata.

This is a convention, not a contract restriction. The contract accepts any
`bytes32` `docChainId`. First use does not create ownership, reserve a name, or
make a profile canonical. A `docChainId` becomes meaningful only when clients,
relayers, indexers, viewers, and communities choose to resolve it as a
particular profile.

This means squatting and pollution are possible at the raw event-log level:
anyone can publish signed claims under any `docChainId`. Profile-aware readers
must ignore or mark invalid events that do not satisfy the profile's rules.
For production profiles, use a stable, versioned profile URI and create a new
URI/`docChainId` when validation rules change incompatibly; do not silently
change the meaning of an existing ID.

For example, RSO can define:

```text
contentHash = SHA-256(canonical catalog JSON)
parentHash = prior RSO DocBlock blockHash
docRef = UTC snapshot-boundary timestamp
docChainId = keccak256("https://om.pub/rso/docchain/v1")
canonical branch = highest eligible card-specific TDH at attestation block time
```

Another chain can use a different NFT collection, an allowlist, institutional
votes, or no winner at all.

## Direct Submission And Relayers

The contract is neutral. A direct submission and a relayed submission are both
signed claims until a viewer, indexer, relayer, or operator validates them
against the relevant `docChainId` profile. A direct submission can put any
profile-shaped claim onchain if the signature is valid and the duplicate key
is unused.

Relayers can add project-specific preflight checks before paying gas, such as
artifact fetching, URI allowlists, sponsorship quotas, reputation thresholds, or
branch-policy validation. Those checks do not change contract validity; they
only decide whether that relayer is willing to spend gas.
