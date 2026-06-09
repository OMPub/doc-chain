# Changelog

## Unreleased — contract release 2

Added:

- `attestBatch`: submit many signed attestations in one transaction (mixed
  attesters allowed). All-or-nothing on validity; already-recorded items are
  skipped, so resubmitting a partially landed batch is idempotent even after
  the recorded items' deadlines pass. Enables a late-joining node to land its
  whole from-genesis chain in a single transaction (~2.36M gas for 51 days).
- `CONTRACT_VERSION` constant ("2"). The EIP-712 domain version stays "1":
  the attestation struct and signing semantics are unchanged, and
  cross-deployment replay is already impossible because `verifyingContract`
  is part of the domain. Existing signing tooling and fixtures stay valid.

Changed:

- `attestDoc` now routes through the shared `_attestOne` path. One observable
  ordering change: an attestation that is both already recorded and past its
  deadline now reverts `DuplicateAttestation` instead of `DeadlineExpired`
  (the duplicate is the more fundamental fact).

## Contract release 1 — deployed to Sepolia 2026-06-07

Added:

- dependency-free `DocChain` Solidity implementation
- Foundry configuration, tests, and deployment script
- direct `solc` build target
- Slither configuration and CI job
- committed canonical ABI at `abi/DocChain.json`
- deterministic EIP-712 fixture at `fixtures/doc-attestation.json`
- stdlib-only ABI check script
- deployment registry documentation
- threat model and release checklist

Security:

- EIP-1271 return data handling now extracts the returned magic value
  explicitly from memory after checking the returned byte length.
