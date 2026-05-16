PYTHON ?= python3
HOMEBREW_PREFIX ?= $(shell if [ -d /opt/homebrew/bin ]; then printf /opt/homebrew; elif [ -d /usr/local/bin ]; then printf /usr/local; fi)
SOLC ?= $(shell if command -v solc >/dev/null 2>&1; then command -v solc; elif [ -n "$(HOMEBREW_PREFIX)" ] && [ -x "$(HOMEBREW_PREFIX)/bin/solc" ]; then printf "$(HOMEBREW_PREFIX)/bin/solc"; else printf solc; fi)
SLITHER ?= $(shell if command -v slither >/dev/null 2>&1; then command -v slither; elif [ -n "$(HOMEBREW_PREFIX)" ] && [ -x "$(HOMEBREW_PREFIX)/bin/slither" ]; then printf "$(HOMEBREW_PREFIX)/bin/slither"; else printf slither; fi)
ENV_FILE ?= .env
LOAD_ENV = set -a; if [ -f "$(ENV_FILE)" ]; then . "$(ENV_FILE)"; fi; set +a;

FOUNDRY_BIN ?= $(HOME)/.foundry/bin
FORGE ?= $(FOUNDRY_BIN)/forge
CAST ?= $(FOUNDRY_BIN)/cast
ifneq ($(HOMEBREW_PREFIX),)
PATH := $(FOUNDRY_BIN):$(HOMEBREW_PREFIX)/bin:$(HOMEBREW_PREFIX)/sbin:$(PATH)
else
PATH := $(FOUNDRY_BIN):$(PATH)
endif
export PATH
SOLC_EVM_VERSION ?= paris
SOLC_BUILD_DIR ?= build/solc
SOLC_SOURCES := $(shell find contracts/src -name '*.sol' -print)
CONTRACT_ABI := abi/DocChain.json
GENERATED_ABI := $(SOLC_BUILD_DIR)/DocChain.abi
FORGE_ARTIFACT := out/DocChain.sol/DocChain.json
SEPOLIA_CHAIN_ID := 11155111
INDEX_ARGS ?=
PREPARED_ATTESTATION ?= build/attestations/attestation.prepared.json
SIGNED_ATTESTATION ?= build/attestations/attestation.signed.json
PREPARE_ATTESTATION_ARGS ?=
SIGN_ATTESTATION_ARGS ?=
SUBMIT_ATTESTATION_ARGS ?=

.PHONY: abi abi-check analyze build build-solc check clean coverage deploy-dry-run
.PHONY: abi-check-forge deploy-sepolia deploy-testnet fmt fmt-check index-events
.PHONY: prepare-attestation sign-attestation submit-attestation test test-python

build:
	$(FORGE) build

build-solc:
	mkdir -p $(SOLC_BUILD_DIR)
	$(SOLC) --base-path . --evm-version $(SOLC_EVM_VERSION) \
		--optimize --abi --bin --overwrite --output-dir $(SOLC_BUILD_DIR) \
		$(SOLC_SOURCES)

test:
	$(FORGE) test

test-python:
	$(PYTHON) -m unittest discover -s tests

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
	@$(LOAD_ENV) \
	if [ -z "$$PRIVATE_KEY" ]; then \
		echo "Set PRIVATE_KEY before deploy-testnet"; \
		exit 1; \
	fi
	@$(LOAD_ENV) \
	if [ -z "$$RPC_URL" ]; then \
		echo "Set RPC_URL before deploy-testnet"; \
		exit 1; \
	fi
	@$(LOAD_ENV) \
	if [ -z "$$EXPECTED_CHAIN_ID" ]; then \
		echo "Set EXPECTED_CHAIN_ID=<chain id> before deploy-testnet"; \
		exit 1; \
	fi
	@$(LOAD_ENV) \
	actual="$$($(CAST) chain-id --rpc-url "$$RPC_URL")"; \
	if [ "$$actual" != "$$EXPECTED_CHAIN_ID" ]; then \
		echo "Refusing deploy-testnet: expected chain $$EXPECTED_CHAIN_ID, got $$actual"; \
		exit 1; \
	fi
	@$(LOAD_ENV) \
	$(FORGE) script contracts/script/DeployDocChain.s.sol:DeployDocChain \
		--rpc-url "$$RPC_URL" --broadcast

deploy-sepolia:
	@$(LOAD_ENV) \
	if [ -z "$$PRIVATE_KEY" ]; then \
		echo "Set PRIVATE_KEY before deploy-sepolia"; \
		exit 1; \
	fi
	@$(LOAD_ENV) \
	if [ -z "$$SEPOLIA_RPC_URL" ]; then \
		echo "Set SEPOLIA_RPC_URL before deploy-sepolia"; \
		exit 1; \
	fi
	@$(LOAD_ENV) \
	actual="$$($(CAST) chain-id --rpc-url "$$SEPOLIA_RPC_URL")"; \
	if [ "$$actual" != "$(SEPOLIA_CHAIN_ID)" ]; then \
		echo "Refusing deploy-sepolia: expected chain $(SEPOLIA_CHAIN_ID), got $$actual"; \
		exit 1; \
	fi
	@$(LOAD_ENV) \
	$(FORGE) script contracts/script/DeployDocChain.s.sol:DeployDocChain \
		--rpc-url "$$SEPOLIA_RPC_URL" --broadcast

deploy-dry-run:
	@$(LOAD_ENV) \
	if [ -z "$$PRIVATE_KEY" ]; then \
		echo "Set PRIVATE_KEY before deploy-dry-run"; \
		exit 1; \
	fi
	@$(LOAD_ENV) \
	if [ -z "$$RPC_URL" ]; then \
		echo "Set RPC_URL before deploy-dry-run"; \
		exit 1; \
	fi
	@$(LOAD_ENV) \
	$(FORGE) script contracts/script/DeployDocChain.s.sol:DeployDocChain \
		--rpc-url "$$RPC_URL"

analyze:
	$(SLITHER) contracts/src/DocChain.sol --config-file slither.config.json \
		--compile-force-framework solc \
		--solc $(SOLC) --solc-args "--base-path . --evm-version $(SOLC_EVM_VERSION) --optimize" \
		--exclude timestamp

index-events:
	@$(LOAD_ENV) $(PYTHON) scripts/index_events.py $(INDEX_ARGS)

prepare-attestation:
	@$(LOAD_ENV) $(PYTHON) scripts/prepare_attestation.py \
		--out $(PREPARED_ATTESTATION) $(PREPARE_ATTESTATION_ARGS)

sign-attestation:
	@$(LOAD_ENV) $(PYTHON) scripts/sign_attestation.py $(PREPARED_ATTESTATION) \
		--out $(SIGNED_ATTESTATION) $(SIGN_ATTESTATION_ARGS)

submit-attestation:
	@$(LOAD_ENV) $(PYTHON) scripts/submit_attestation.py $(SIGNED_ATTESTATION) \
		$(SUBMIT_ATTESTATION_ARGS)

check: build test test-python fmt-check abi-check abi-check-forge analyze

clean:
	rm -rf out cache build broadcast
