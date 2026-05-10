# Release Checklist

Use this checklist before tagging a contract release or deploying a new
`DocChain` instance.

## Source Freeze

- confirm protocol docs match the contract ABI
- confirm `DocChain.VERSION()` is correct for the release
- run `make abi-check`
- run `make fmt-check`
- run `make check`
- run `make build`
- run `make test`
- run `make coverage`
- run `make build-solc`
- run `make abi-check-forge` if native `solc` 0.8.35 is unavailable
- run `make analyze`
- review `git diff` for unrelated edits

## Audit Readiness

- update `docs/audit.md`
- update `docs/threat-model.md` if assumptions changed
- verify all expected revert paths have tests
- verify fixture values against independent Ethereum tooling if typed-data
  fields changed
- verify the committed ABI is generated from the frozen source

## Testnet Deployment

- deploy to Sepolia first unless the use case specifically needs Hoodi
- use a non-mainnet deployer key
- verify source on the explorer
- submit at least one EOA attestation
- submit at least one EIP-1271 attestation
- confirm emitted `DocAttested` logs match the fixture shape
- commit the deployment JSON under `deployments/`

## Mainnet Deployment

- confirm the deployment commit is tagged
- confirm all CI jobs pass on the tagged commit
- use a hardware-backed or otherwise isolated deployer key
- verify source immediately after deployment
- publish chain ID, contract address, tx hash, ABI, and source commit
- archive deployment logs in the project release notes

## Post-Deploy

- monitor explorer verification status
- monitor first production attestations
- publish any profile-specific relayer rules separately from contract docs
- create a new `docChainId` profile if validation rules changed
  incompatibly
