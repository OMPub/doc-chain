# Deployments

This directory is the deployment registry for `DocChain` instances.
Commit one JSON file per deployed network after source verification succeeds.

Recommended names:

```text
sepolia.json
hoodi.json
mainnet.json
```

Each file should use this shape:

```json
{
  "contract": "DocChain",
  "version": "1",
  "chainId": 11155111,
  "network": "sepolia",
  "address": "0x...",
  "transactionHash": "0x...",
  "deployer": "0x...",
  "blockNumber": 0,
  "compiler": {
    "solc": "0.8.35",
    "evmVersion": "paris",
    "optimizer": true,
    "optimizerRuns": 200
  },
  "source": {
    "commit": "0x...",
    "verifiedUrl": "https://..."
  },
  "deployedAt": "YYYY-MM-DDTHH:MM:SSZ"
}
```

Do not commit private keys, RPC URLs, or deployment mnemonics.
