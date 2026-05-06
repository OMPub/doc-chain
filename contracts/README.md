# Contracts

Contract source will live here once the protocol ABI is finalized. The contract
boundary is intentionally small: one write function and one append-only event.

## Write Surface

```solidity
attestDocument(
    DocumentAttestation calldata attestation,
    bytes calldata signature
)
```

`attestation.attester` is the signer. `msg.sender` is only the submitter/gas
payer and can be the attester, a relayer, a GitHub Action, or another courier.

The implementation must:

- verify EIP-712 signatures for EOAs
- verify EIP-1271 signatures for contract wallets
- reject expired deadlines
- reject URIs longer than 8192 bytes
- compute `blockHash = hashStruct(attestation.docBlock)`
- compute `uriHash = keccak256(bytes(attestation.uri))`
- reject duplicate `(attester, docChainId, docRef, parentHash,
  contentHash, uriHash)` claims
- emit `DocumentAttested`

## Event

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
