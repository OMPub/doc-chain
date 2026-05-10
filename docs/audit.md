# Solidity Audit Notes

Manual review date: 2026-05-08

Scope:

- `contracts/src/DocChain.sol`
- `contracts/test/DocChain.t.sol`
- EIP-712 hashing and replay domain
- EOA and EIP-1271 signature verification
- deadline enforcement
- duplicate-prevention key
- event data completeness
- URI length bound

Not in scope:

- profile-specific doc validation
- canonical branch selection
- URI reachability or content fetching
- relayer sponsorship rules
- third-party wallet implementation correctness

## Summary

No high, medium, or low severity issues are open in the reviewed contract
scope.

The contract matches the protocol boundary: it records signed claims, enforces
signature validity and uniqueness, emits an append-only event, and leaves
profile validation to off-chain clients.

## Security Properties Reviewed

Replay protection:

- EIP-712 domain includes `name`, `version`, `chainId`, and
  `verifyingContract`.
- Domain separator is cached for gas but recomputed if `block.chainid` changes.

Signature verification:

- EOAs recover from the EIP-712 digest, not an Ethereum signed-message digest.
- Both 65-byte signatures and EIP-2098 64-byte compact signatures are accepted.
- EOA signatures reject invalid `v` values and high-`s` malleable signatures.
- Contract wallets are verified with `isValidSignature(bytes32,bytes)` and the
  EIP-1271 magic value.
- EIP-1271 return data is length-checked before extracting the magic value.
- `address(0)` is rejected as an attester.

State and duplicate handling:

- Duplicate key is `keccak256(abi.encode(attester, docChainId, docRef,
  parentHash, contentHash, uriHash))`.
- State is changed only after all validation succeeds.
- The only external call is a `staticcall` to EIP-1271 before state mutation.

Bounds and event completeness:

- `bytes(uri).length` must be at most 8192.
- `uriHash` is computed by the contract from the submitted URI.
- Event includes submitter, parent hash, block hash, content hash, URI hash, and
  URI.

## Informational Notes

URI normalization is intentionally out of scope. Different URI strings that
resolve to the same bytes are distinct publication claims because the duplicate
key uses `uriHash`.

The same attester may attest the same doc block with different URIs. This
matches the protocol requirement for IPFS, Arweave, HTTPS, and hash-only
publication variants.

EIP-1271 validation is checked at submission time. A contract wallet changing
its signing policy later does not invalidate historical events.

## Verification Performed

Compiler target:

- `solc` 0.8.35

Commands run successfully:

```bash
make build
make test
make check
forge test -vvv --fuzz-runs 1024
make coverage
make analyze
make abi-check
make abi-check-forge
solc --base-path . --evm-version paris --optimize --abi --bin --overwrite --output-dir build/solc-test contracts/test/DocChain.t.sol
solc --base-path . --evm-version paris --optimize --abi --bin --overwrite --output-dir build/solc-script contracts/script/DeployDocChain.s.sol
python3 -m json.tool abi/DocChain.json
python3 -m json.tool fixtures/doc-attestation.json
python3 -m py_compile scripts/check_abi.py reference/docchain/*.py
```

Coverage summary for `contracts/src/DocChain.sol`:

- 100% line coverage
- 100% statement coverage
- 100% branch coverage
- 100% function coverage

Slither 0.11.5 reported zero findings with the timestamp detector excluded.
That exclusion is intentional because signature deadlines use Ethereum's
consensus timestamp by design; the deadline boundary and expired-deadline paths
are covered by tests.

## Pre-Deploy Checklist

Before mainnet or production testnet use:

- run `make test` with Foundry installed
- run `make analyze` with Slither installed
- verify off-chain typed-data signing against `attestationDigest`
- deploy first to Sepolia with a non-mainnet key
- verify source on the target explorer
- publish the deployed address, chain ID, and contract version with the
  relevant `docChainId` profile documentation
