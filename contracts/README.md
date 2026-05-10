# Contracts

Contract source lives in `contracts/src`. The project uses a dependency-free
Foundry layout: Solidity code imports only local files, tests define their own
minimal cheatcode interface, and deployment scripts do not import `forge-std`.

## Write Surface

```solidity
attestDoc(
    DocAttestation calldata attestation,
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
- emit `DocAttested`

## Layout

```text
contracts/src/DocChain.sol              production contract
contracts/test/DocChain.t.sol           Foundry tests, no forge-std
contracts/script/DeployDocChain.s.sol   Foundry broadcast script
```

## Commands

```bash
make check        # build, test, fmt-check, ABI checks, and Slither
make build-solc   # compile production Solidity with native solc 0.8.35
make build        # compile with Foundry
make test         # run Foundry tests
make coverage     # run Foundry coverage summary
make abi-check    # check committed ABI against solc output
make abi-check-forge
make analyze      # run Slither against contracts/src/DocChain.sol
```

Deployment uses `PRIVATE_KEY` from the environment:

```bash
SEPOLIA_RPC_URL=https://... PRIVATE_KEY=0x... make deploy-sepolia
RPC_URL=https://... EXPECTED_CHAIN_ID=12345 PRIVATE_KEY=0x... make deploy-testnet
```

## Event

```solidity
event DocAttested(
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
