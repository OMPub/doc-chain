"""Document Chain ABI constants used by stdlib indexers."""

MAX_URI_BYTES = 8192

EIP712_DOMAIN_TYPE = (
    "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
)

DOC_BLOCK_TYPE = (
    "DocBlock(bytes32 docChainId,uint64 docRef,bytes32 parentHash,bytes32 contentHash)"
)

DOCUMENT_ATTESTATION_TYPE = (
    "DocumentAttestation(address attester,DocBlock docBlock,string uri,uint256 deadline)"
    + DOC_BLOCK_TYPE
)

DOCUMENT_ATTESTED_EVENT = (
    "DocumentAttested(bytes32,address,uint64,address,bytes32,bytes32,bytes32,bytes32,string)"
)
