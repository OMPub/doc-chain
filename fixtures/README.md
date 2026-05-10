# Fixtures

`doc-attestation.json` is a deterministic EIP-712 fixture for
`DocChain`. It includes:

- domain fields
- typed-data strings
- attestation message
- type hashes
- domain separator
- doc block hash
- URI hash
- attestation struct hash
- full EIP-712 digest
- duplicate-prevention key
- deterministic EOA signature

The fixture is intentionally static. If typed-data fields change, regenerate
this file with independent Ethereum tooling and review the full diff. The repo
does not ship local Keccak-256 or secp256k1 implementations for fixture
generation.
