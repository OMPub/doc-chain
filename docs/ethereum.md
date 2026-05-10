# Ethereum Project

Doc Chain is set up as a dependency-free Solidity project. The repository
does not vendor OpenZeppelin, forge-std, npm packages, or generated libraries.
External tools are expected to be installed on the operator's machine.

## Tooling

Required for local Ethereum development:

- `solc` 0.8.35 for direct compiler checks
- Foundry (`forge`) for tests, scripts, and broadcast deployments
- Slither for static analysis

The repo includes:

```text
foundry.toml                            Foundry compiler and path settings
Makefile                                common build, test, deploy, and analysis targets
slither.config.json                     Slither path filtering
abi/DocChain.json                       committed canonical ABI
fixtures/doc-attestation.json           deterministic EIP-712 fixture
contracts/src/DocChain.sol              production contract
contracts/test/DocChain.t.sol           dependency-free Foundry tests
contracts/script/DeployDocChain.s.sol
```

## Build And Test

Compile with native `solc` 0.8.35:

```bash
make build-solc
```

Compile and run the full Foundry test suite:

```bash
make build
make test
```

Run the standard local validation suite:

```bash
make check
```

Run the coverage summary:

```bash
make coverage
```

Check generated artifacts:

```bash
make abi-check
```

Without native `solc` 0.8.35, use Foundry's compiler artifact instead:

```bash
make abi-check-forge
```

The tests cover:

- EOA EIP-712 attestation
- EIP-2098 compact EOA signatures
- EIP-1271 contract-wallet attestation
- EIP-1271 rejection
- duplicate rejection
- same doc block with a different URI
- expired deadline rejection
- exact-deadline acceptance
- empty URI acceptance
- max-length URI acceptance
- URI cap rejection
- malformed EOA signature rejection
- high-`s` EOA signature rejection
- wrong-signer rejection
- zero-attester rejection
- cross-deployment domain replay rejection
- EIP-712 domain separator fields

## CI

The GitHub Actions workflow at `.github/workflows/solidity.yml` runs:

- `make fmt-check`
- `forge build --sizes`
- `forge test -vvv`
- `make abi-check-forge`
- Slither against `contracts/src/DocChain.sol`

## Static Analysis

Run Slither against the production contract:

```bash
make analyze
```

The Slither target intentionally analyzes `contracts/src/DocChain.sol`
instead of test or script helpers.

## ABI And Fixtures

Regenerate the committed ABI after any contract ABI change:

```bash
make abi
```

If you do not have native `solc` 0.8.35 installed, use Foundry for the check:

```bash
make abi-check-forge
```

The EIP-712 fixture in `fixtures/doc-attestation.json` is intentionally a
static cross-implementation vector. Regenerate it with independent Ethereum
tooling when the typed-data shape changes, then review the diff. The repo does
not maintain local Keccak-256 or secp256k1 implementations just for fixture
generation.

## Testnet Deployment

Use Sepolia for application-contract testing. Use Hoodi only when the workflow
specifically needs the maintained staking/protocol testnet. Check the
[ethereum.org networks page](https://ethereum.org/developers/docs/networks/)
before deployment; as of 2026-05-06, Holesky is deprecated.

```bash
SEPOLIA_RPC_URL=https://... PRIVATE_KEY=0x... make deploy-sepolia
HOODI_RPC_URL=https://... PRIVATE_KEY=0x... make deploy-hoodi
```

For any EVM-compatible testnet, use a direct RPC URL:

```bash
RPC_URL=https://... EXPECTED_CHAIN_ID=12345 PRIVATE_KEY=0x... make deploy-testnet
```

The deploy script reads `PRIVATE_KEY` inside Foundry and broadcasts
`new DocChain()`. Keep private keys in the local shell or an untracked
`.env` file.
The deployment Make targets preflight `cast chain-id` before broadcasting:
Sepolia must report `11155111`, Hoodi must report `560048`, and generic
testnet deployments must provide `EXPECTED_CHAIN_ID`.

After deployment and source verification, commit a deployment registry file
under `deployments/`.

## Verification

After deployment, verify with the explorer for the target chain. With Foundry:

```bash
forge verify-contract \
  --chain sepolia \
  <DEPLOYED_ADDRESS> \
  contracts/src/DocChain.sol:DocChain
```

Set `ETHERSCAN_API_KEY` when using an Etherscan-compatible verifier.
