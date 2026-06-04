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

## Event Indexing

The generic indexer is dependency-free and uses raw Ethereum JSON-RPC:

```bash
python3 scripts/index_events.py \
  --rpc-url https://... \
  --address 0x... \
  --from-block 123456 \
  --format jsonl
```

It can also print just the Ethereum block numbers that contain attestations:

```bash
python3 scripts/index_events.py \
  --rpc-url https://... \
  --address 0x... \
  --from-block 123456 \
  --format blocks
```

For long-running jobs, use confirmations and a checkpoint:

```bash
python3 scripts/index_events.py \
  --deployment deployments/sepolia.json \
  --rpc-url "$SEPOLIA_RPC_URL" \
  --confirmations 12 \
  --checkpoint .docchain-sepolia.checkpoint.json \
  --format jsonl
```

Checkpoints record the contract address and topic filters. Reuse a checkpoint
only with the same address, `docChainId`, attester, and `docRef` filter set.

The indexer has built-in provider backoff. It retries HTTP/JSON-RPC 429
responses with exponential backoff and jitter, pauses briefly between
`eth_getLogs` requests, and only splits block ranges for non-rate-limit RPC
errors such as provider range limits.

Topic filters are available for `docChainId`, `attester`, and `docRef`:

```bash
python3 scripts/index_events.py \
  --deployment deployments/sepolia.json \
  --rpc-url "$SEPOLIA_RPC_URL" \
  --doc-chain-id 0x... \
  --doc-ref 20260511000000
```

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

Use Sepolia for application-contract testing. For any other EVM-compatible
testnet, use the generic `deploy-testnet` target with an explicit chain ID.

```bash
SEPOLIA_RPC_URL=https://... PRIVATE_KEY=0x... make deploy-sepolia
```

Operator targets source an ignored local `.env` file inside the recipe shell, so
operators can copy `.env.example`, fill in local values, and run the same
targets without exporting variables in each shell. The Makefile intentionally
does not parse `.env` as Make syntax, which avoids exposing key material through
Make introspection output.

For any EVM-compatible testnet, use a direct RPC URL:

```bash
RPC_URL=https://... EXPECTED_CHAIN_ID=12345 PRIVATE_KEY=0x... make deploy-testnet
```

Before broadcasting a generic deployment, run a dry-run against the target RPC:

```bash
RPC_URL=https://... PRIVATE_KEY=0x... make deploy-dry-run
```

The deploy script reads `PRIVATE_KEY` inside Foundry and broadcasts
`new DocChain()`. Keep private keys in the local shell or an untracked
`.env` file.
The deployment Make targets check required environment values and preflight
`cast chain-id` before broadcasting: Sepolia must report `11155111`, and generic
testnet deployments must provide `EXPECTED_CHAIN_ID`.

After deployment and source verification, commit a deployment registry file
under `deployments/`.

The event indexer can use the registry file directly. Its `blockNumber` value is
used as the default scan start block.

## Attestation Workflow

The repo keeps attestation preparation, signing, and submission separate:

- `scripts/prepare_attestation.py` writes EIP-712 typed data and never handles a
  private key.
- `scripts/sign_attestation.py` signs the typed data with Foundry `cast`.
- `scripts/submit_attestation.py` submits the signed envelope with Foundry
  `cast`.

Set an attester address in your shell or `.env`:

```bash
DOCCHAIN_ATTESTER=0x...
```

Optionally set an identity address the attester is speaking for. Omit this, or
use `0x0000000000000000000000000000000000000000`, when no delegated identity is
claimed:

```bash
DOCCHAIN_ON_BEHALF_OF=0x...
```

Prepare typed data:

```bash
make prepare-attestation PREPARE_ATTESTATION_ARGS="\
--deployment deployments/sepolia.json \
--doc-chain-id 0x... \
--doc-ref 20260514000000 \
--content-hash 0x... \
--uri ar://..."
```

This writes `build/attestations/attestation.prepared.json`.
Pass `--attester 0x...` in `PREPARE_ATTESTATION_ARGS` if you do not set
`DOCCHAIN_ATTESTER`. Pass `--on-behalf-of 0x...` or set
`DOCCHAIN_ON_BEHALF_OF` if the signed attestation should point to a delegated
identity.

Sign it:

```bash
make sign-attestation
```

This reads `PRIVATE_KEY` by default and writes
`build/attestations/attestation.signed.json`. For a prompt instead of an
environment variable:

```bash
python3 scripts/sign_attestation.py --interactive
```

Simulate submission:

```bash
make submit-attestation SUBMIT_ATTESTATION_ARGS="--dry-run"
```

Broadcast submission:

```bash
make submit-attestation
```

The submitter can be different from the attester. `submit_attestation.py` uses
`SUBMITTER_PRIVATE_KEY` if set, otherwise it falls back to `PRIVATE_KEY`.

## Verification

After deployment, verify with the explorer for the target chain. With Foundry:

```bash
forge verify-contract \
  --chain sepolia \
  <DEPLOYED_ADDRESS> \
  contracts/src/DocChain.sol:DocChain
```

Set `ETHERSCAN_API_KEY` when using an Etherscan-compatible verifier.
