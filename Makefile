SOLC ?= solc
FOUNDRY_BIN ?= $(HOME)/.foundry/bin
FORGE ?= $(FOUNDRY_BIN)/forge
CAST ?= $(FOUNDRY_BIN)/cast
SLITHER ?= slither
PATH := $(FOUNDRY_BIN):$(PATH)
export PATH
SOLC_EVM_VERSION ?= paris
SOLC_BUILD_DIR ?= build/solc
SOLC_SOURCES := $(shell find contracts/src -name '*.sol' -print)
CONTRACT_ABI := abi/DocChain.json
GENERATED_ABI := $(SOLC_BUILD_DIR)/DocChain.abi
FORGE_ARTIFACT := out/DocChain.sol/DocChain.json
SEPOLIA_CHAIN_ID := 11155111
HOODI_CHAIN_ID := 560048

.PHONY: abi abi-check analyze build build-solc check clean coverage deploy-hoodi
.PHONY: abi-check-forge deploy-sepolia deploy-testnet fmt fmt-check test

build:
	$(FORGE) build

build-solc:
	mkdir -p $(SOLC_BUILD_DIR)
	$(SOLC) --base-path . --evm-version $(SOLC_EVM_VERSION) \
		--optimize --abi --bin --overwrite --output-dir $(SOLC_BUILD_DIR) \
		$(SOLC_SOURCES)

test:
	$(FORGE) test

coverage:
	RUST_LOG=error $(FORGE) coverage --report summary --skip script

fmt:
	$(FORGE) fmt

fmt-check:
	$(FORGE) fmt --check

abi: build-solc
	mkdir -p abi
	python3 -m json.tool $(GENERATED_ABI) $(CONTRACT_ABI)

abi-check: build-solc
	python3 scripts/check_abi.py $(GENERATED_ABI) $(CONTRACT_ABI)

abi-check-forge:
	$(FORGE) build
	python3 scripts/check_abi.py $(FORGE_ARTIFACT) $(CONTRACT_ABI)

deploy-testnet:
	@if [ -z "$(EXPECTED_CHAIN_ID)" ]; then \
		echo "Set EXPECTED_CHAIN_ID=<chain id> before deploy-testnet"; \
		exit 1; \
	fi
	@actual="$$($(CAST) chain-id --rpc-url "$(RPC_URL)")"; \
	if [ "$$actual" != "$(EXPECTED_CHAIN_ID)" ]; then \
		echo "Refusing deploy-testnet: expected chain $(EXPECTED_CHAIN_ID), got $$actual"; \
		exit 1; \
	fi
	$(FORGE) script contracts/script/DeployDocChain.s.sol:DeployDocChain \
		--rpc-url "$(RPC_URL)" --broadcast

deploy-sepolia:
	@actual="$$($(CAST) chain-id --rpc-url sepolia)"; \
	if [ "$$actual" != "$(SEPOLIA_CHAIN_ID)" ]; then \
		echo "Refusing deploy-sepolia: expected chain $(SEPOLIA_CHAIN_ID), got $$actual"; \
		exit 1; \
	fi
	$(FORGE) script contracts/script/DeployDocChain.s.sol:DeployDocChain \
		--rpc-url sepolia --broadcast

deploy-hoodi:
	@actual="$$($(CAST) chain-id --rpc-url hoodi)"; \
	if [ "$$actual" != "$(HOODI_CHAIN_ID)" ]; then \
		echo "Refusing deploy-hoodi: expected chain $(HOODI_CHAIN_ID), got $$actual"; \
		exit 1; \
	fi
	$(FORGE) script contracts/script/DeployDocChain.s.sol:DeployDocChain \
		--rpc-url hoodi --broadcast

analyze:
	$(SLITHER) contracts/src/DocChain.sol --config-file slither.config.json \
		--compile-force-framework solc \
		--solc $(SOLC) --solc-args "--base-path . --evm-version $(SOLC_EVM_VERSION) --optimize" \
		--exclude timestamp

check: build test fmt-check abi-check abi-check-forge analyze

clean:
	rm -rf out cache build broadcast
