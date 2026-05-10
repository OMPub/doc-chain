# Changelog

## Unreleased

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
