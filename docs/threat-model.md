# Threat Model

This doc describes the security boundary for `DocChain`.

## Assets

- integrity of attestation events
- replay resistance across chains and deployments
- correctness of duplicate-prevention keys
- correctness of signer attribution
- bounded event payload size

## Trusted Inputs

The contract trusts only Ethereum consensus and successful signature
verification. It does not trust `msg.sender` as the attester and it does not
trust URI contents.

## Actors

Attester:

- signs an EIP-712 `DocAttestation`
- may be an EOA or an EIP-1271 contract wallet

Submitter:

- pays gas to submit a signed attestation
- may be the attester, a relayer, an automation, or any other courier

Indexer:

- reads `DocAttested` logs
- applies profile-specific validation outside the contract

Profile:

- defines the meaning of `docChainId`, `docRef`, `contentHash`, URIs,
  eligibility, and branch scoring

## Threats And Mitigations

Cross-chain or cross-contract replay:

- mitigated by EIP-712 domain fields `chainId` and `verifyingContract`

Wrong signer attribution:

- mitigated by making `attester` part of the signed payload and verifying
  against that address

Contract-wallet signature mismatch:

- mitigated by using EIP-1271 `isValidSignature(bytes32,bytes)` for attesters
  with code

Signature malleability:

- mitigated for EOAs by rejecting high-`s` signatures and invalid `v` values

Duplicate publication spam by identical claim:

- mitigated by storing `keccak256(abi.encode(attester, docChainId, docRef,
  parentHash, contentHash, uriHash))`

Unbounded URI payloads:

- mitigated by rejecting URIs longer than 8192 bytes

Profile pollution:

- not prevented by the contract. Any valid signer can publish under any
  `docChainId`; profile-aware readers must filter invalid or ineligible events.

Invalid external doc bytes:

- not prevented by the contract. Smart contracts cannot fetch IPFS, Arweave,
  HTTPS, or application APIs. Clients must validate fetched bytes offchain.

Canonical branch manipulation:

- not prevented by the contract. Branch choice is a profile rule, not a
  contract rule.

## Non-Goals

The contract does not:

- fetch or validate URI contents
- choose a canonical branch
- define eligible attesters
- reserve or own `docChainId` values
- rate-limit submitters
- sponsor gas
- make EIP-1271 signatures immutable after submission
