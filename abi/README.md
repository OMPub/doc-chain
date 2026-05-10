# ABI

`DocChain.json` is the committed canonical ABI generated from
`contracts/src/DocChain.sol`.

Regenerate it with:

```bash
make abi
```

Check it against `solc` output with:

```bash
make abi-check
```
