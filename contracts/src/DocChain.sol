// SPDX-License-Identifier: CC0-1.0
pragma solidity 0.8.35;

/*

        .          *                 .                 *          .
   *          .             .                 .                .
                         .      .   *   .      .
                    .       .     *     .       .
              .          .    *   .   *    .          .
                         .      .   *   .      .
        .                    .           .                    *
      .--------.      .--------.      .--------.      .--------.
      |       /|      |       /|      |       /|      |       /|
      |   D    |------|   C    |------|   A    |------|   P    |-->>
      |        |      |        |      |        |      |        |
      '--------'      '--------'      '--------'      '--------'
        .                    .           .                    *
                         .      .   *   .      .
              .          .    *   .   *    .          .
                    .       .     *     .       .
                         .      .   *   .      .
   *          .             .                 .                .
        .          *                 .                 *          .

*/

/// @title Doc Chain
/// @notice Append-only witness log for EIP-712 signed doc-chain attestations.
contract DocChain {
    string public constant NAME = "Doc Chain";
    // EIP-712 domain version. Stays "1": the DocAttestation struct and signing
    // semantics are unchanged across contract releases, and cross-deployment
    // replay is already impossible because verifyingContract is in the domain.
    string public constant VERSION = "1";
    // Contract feature release. "2" adds attestBatch (batch courier submission).
    string public constant CONTRACT_VERSION = "2";

    uint256 public constant MAX_URI_BYTES = 8192;

    bytes32 public constant EIP712_DOMAIN_TYPEHASH = keccak256(
        "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    );
    bytes32 public constant DOC_BLOCK_TYPEHASH = keccak256(
        "DocBlock(bytes32 docChainId,uint64 docRef,bytes32 parentHash,bytes32 contentHash)"
    );
    bytes32 public constant DOC_ATTESTATION_TYPEHASH = keccak256(
        "DocAttestation(address attester,address onBehalfOf,DocBlock docBlock,string uri,uint256 deadline)"
        "DocBlock(bytes32 docChainId,uint64 docRef,bytes32 parentHash,bytes32 contentHash)"
    );

    // EIP-1271 magic value: bytes4(keccak256("isValidSignature(bytes32,bytes)")).
    bytes4 private constant EIP1271_MAGIC_VALUE = 0x1626ba7e;
    // EIP-2098 stores v in the top bit of s; this mask clears that bit.
    bytes32 private constant EIP2098_S_MASK =
        0x7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff;
    uint256 private constant SECP256K1_HALF_ORDER =
        0x7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0;

    bytes32 private immutable cachedDomainSeparator;
    uint256 private immutable cachedChainId;

    mapping(bytes32 attestationKey => bool exists) public attested;

    struct DocBlock {
        bytes32 docChainId;
        uint64 docRef;
        bytes32 parentHash;
        bytes32 contentHash;
    }

    struct DocAttestation {
        address attester;
        address onBehalfOf;
        DocBlock docBlock;
        string uri;
        uint256 deadline;
    }

    event DocAttested(
        bytes32 indexed docChainId,
        address indexed attester,
        uint64 indexed docRef,
        address onBehalfOf,
        address submitter,
        bytes32 parentHash,
        bytes32 blockHash,
        bytes32 contentHash,
        bytes32 uriHash,
        string uri
    );

    error InvalidAttester();
    error DeadlineExpired(uint256 deadline, uint256 currentTime);
    error UriTooLong(uint256 length, uint256 maxLength);
    error DuplicateAttestation(bytes32 attestationKey);
    error InvalidSignature(address attester);
    error InvalidSignatureLength(uint256 length);
    error EmptyBatch();
    error BatchLengthMismatch(uint256 attestationsLength, uint256 signaturesLength);

    constructor() {
        cachedChainId = block.chainid;
        cachedDomainSeparator = _buildDomainSeparator();
    }

    /// @notice Submit a signed doc attestation on behalf of any valid attester.
    /// @dev `msg.sender` is only the gas payer/courier. The signer is `attestation.attester`.
    function attestDoc(DocAttestation calldata attestation, bytes calldata signature)
        external
        returns (bytes32 blockHash, bytes32 uriHash, bytes32 key)
    {
        (, blockHash, uriHash, key) = _attestOne(attestation, signature, false);
    }

    /// @notice Submit many signed doc attestations in a single transaction.
    /// @dev `msg.sender` is only the gas payer/courier; each item carries its own
    /// attester signature, so a batch may mix attesters (e.g. a sweeper submitting
    /// for several nodes, or a late-joining node attesting every day since genesis).
    ///
    /// Semantics: all-or-nothing on validity, idempotent on duplicates. Any invalid
    /// item (bad signature, expired deadline, over-long uri, zero attester) reverts
    /// the whole batch; an item whose attestation key is already recorded is skipped
    /// without re-verification, so resubmitting a partially landed batch -- even one
    /// whose already-recorded items have since passed their deadlines -- succeeds.
    function attestBatch(DocAttestation[] calldata attestations, bytes[] calldata signatures)
        external
        returns (uint256 storedCount, uint256 skippedCount)
    {
        uint256 count = attestations.length;
        if (count == 0) {
            revert EmptyBatch();
        }
        if (count != signatures.length) {
            revert BatchLengthMismatch(count, signatures.length);
        }

        for (uint256 i = 0; i < count; ++i) {
            (bool stored,,,) = _attestOne(attestations[i], signatures[i], true);
            unchecked {
                if (stored) {
                    ++storedCount;
                } else {
                    ++skippedCount;
                }
            }
        }
    }

    /// @dev Shared validation/storage path for single and batch submission. With
    /// `skipDuplicates`, an already-recorded key returns `stored = false` before any
    /// further checks: a recorded key proves an identical claim (same attester,
    /// onBehalfOf, doc block, and uri) already passed validation, so re-checking the
    /// new copy's deadline or signature would only break idempotent resubmission.
    function _attestOne(
        DocAttestation calldata attestation,
        bytes calldata signature,
        bool skipDuplicates
    ) private returns (bool stored, bytes32 blockHash, bytes32 uriHash, bytes32 key) {
        address attester = attestation.attester;

        // ecrecover returns address(0) for invalid signatures, so it cannot be a valid attester.
        if (attester == address(0)) {
            revert InvalidAttester();
        }

        blockHash = _hashDocBlockFields(
            attestation.docBlock.docChainId,
            attestation.docBlock.docRef,
            attestation.docBlock.parentHash,
            attestation.docBlock.contentHash
        );
        uriHash = keccak256(bytes(attestation.uri));
        key = _attestationKeyFields(
            attester,
            attestation.onBehalfOf,
            attestation.docBlock.docChainId,
            attestation.docBlock.docRef,
            attestation.docBlock.parentHash,
            attestation.docBlock.contentHash,
            uriHash
        );

        if (attested[key]) {
            if (skipDuplicates) {
                return (false, blockHash, uriHash, key);
            }
            revert DuplicateAttestation(key);
        }

        // Signature deadlines intentionally use Ethereum's consensus timestamp.
        // slither-disable-start timestamp
        // forge-lint: disable-next-line(block-timestamp)
        if (block.timestamp > attestation.deadline) {
            revert DeadlineExpired(attestation.deadline, block.timestamp);
        }
        // slither-disable-end timestamp

        uint256 uriLength = bytes(attestation.uri).length;
        if (uriLength > MAX_URI_BYTES) {
            revert UriTooLong(uriLength, MAX_URI_BYTES);
        }

        bytes32 structHash = _hashAttestationFields(
            attester, attestation.onBehalfOf, blockHash, uriHash, attestation.deadline
        );
        bytes32 digest = _toTypedDataHash(structHash);
        _requireValidSignature(attester, digest, signature);

        attested[key] = true;
        stored = true;

        _emitDocAttested(attestation, blockHash, uriHash);
    }

    function _emitDocAttested(
        DocAttestation calldata attestation,
        bytes32 blockHash,
        bytes32 uriHash
    ) private {
        emit DocAttested(
            attestation.docBlock.docChainId,
            attestation.attester,
            attestation.docBlock.docRef,
            attestation.onBehalfOf,
            msg.sender,
            attestation.docBlock.parentHash,
            blockHash,
            attestation.docBlock.contentHash,
            uriHash,
            attestation.uri
        );
    }

    /// @notice Current EIP-712 domain separator.
    // slither-disable-next-line naming-convention
    function DOMAIN_SEPARATOR() public view returns (bytes32) {
        if (block.chainid == cachedChainId) {
            return cachedDomainSeparator;
        }

        return _buildDomainSeparator();
    }

    /// @notice EIP-712 `hashStruct(DocBlock)`.
    function hashDocBlock(DocBlock memory docBlock) public pure returns (bytes32) {
        return _hashDocBlockFields(
            docBlock.docChainId, docBlock.docRef, docBlock.parentHash, docBlock.contentHash
        );
    }

    /// @notice EIP-712 `hashStruct(DocAttestation)`.
    function hashAttestation(DocAttestation memory attestation) public pure returns (bytes32) {
        return _hashAttestationFields(
            attestation.attester,
            attestation.onBehalfOf,
            hashDocBlock(attestation.docBlock),
            keccak256(bytes(attestation.uri)),
            attestation.deadline
        );
    }

    /// @notice Full EIP-712 digest that the attester signs.
    function attestationDigest(DocAttestation memory attestation) public view returns (bytes32) {
        return _toTypedDataHash(hashAttestation(attestation));
    }

    /// @notice Duplicate-prevention key for a publication claim.
    function attestationKey(
        address attester,
        address onBehalfOf,
        DocBlock memory docBlock,
        bytes32 uriHash
    ) public pure returns (bytes32) {
        return _attestationKeyFields(
            attester,
            onBehalfOf,
            docBlock.docChainId,
            docBlock.docRef,
            docBlock.parentHash,
            docBlock.contentHash,
            uriHash
        );
    }

    function _attestationKeyFields(
        address attester,
        address onBehalfOf,
        bytes32 docChainId,
        uint64 docRef,
        bytes32 parentHash,
        bytes32 contentHash,
        bytes32 uriHash
    ) private pure returns (bytes32) {
        // Use abi.encode, not abi.encodePacked, to keep the key unambiguous across typed fields.
        return keccak256(
            abi.encode(attester, onBehalfOf, docChainId, docRef, parentHash, contentHash, uriHash)
        );
    }

    function _buildDomainSeparator() private view returns (bytes32) {
        return keccak256(
            abi.encode(
                EIP712_DOMAIN_TYPEHASH,
                keccak256(bytes(NAME)),
                keccak256(bytes(VERSION)),
                block.chainid,
                address(this)
            )
        );
    }

    function _hashDocBlockFields(
        bytes32 docChainId,
        uint64 docRef,
        bytes32 parentHash,
        bytes32 contentHash
    ) private pure returns (bytes32) {
        return keccak256(
            abi.encode(DOC_BLOCK_TYPEHASH, docChainId, docRef, parentHash, contentHash)
        );
    }

    function _hashAttestationFields(
        address attester,
        address onBehalfOf,
        bytes32 blockHash,
        bytes32 uriHash,
        uint256 deadline
    ) private pure returns (bytes32) {
        return keccak256(
            abi.encode(DOC_ATTESTATION_TYPEHASH, attester, onBehalfOf, blockHash, uriHash, deadline)
        );
    }

    function _toTypedDataHash(bytes32 structHash) private view returns (bytes32) {
        return keccak256(abi.encodePacked("\x19\x01", DOMAIN_SEPARATOR(), structHash));
    }

    function _requireValidSignature(address attester, bytes32 digest, bytes calldata signature)
        private
        view
    {
        if (attester.code.length == 0) {
            if (_recoverSigner(digest, signature) != attester) {
                revert InvalidSignature(attester);
            }
            return;
        }

        // EIP-1271 requires calling a wallet-defined validation hook. Reachable
        // from the attestBatch loop, which is safe: a batch submitter chooses its
        // own batch contents, so a misbehaving wallet can only revert a batch that
        // voluntarily includes it, and the call is a staticcall (no reentrancy).
        // slither-disable-next-line low-level-calls,calls-loop
        (bool ok, bytes memory result) =
            attester.staticcall(abi.encodeWithSelector(EIP1271_MAGIC_VALUE, digest, signature));

        if (!ok || result.length < 4) {
            revert InvalidSignature(attester);
        }

        bytes4 magicValue;
        // slither-disable-next-line assembly
        assembly ("memory-safe") {
            // Dynamic bytes are stored as [length][data]; this loads the first data word.
            magicValue := mload(add(result, 0x20))
        }

        if (magicValue != EIP1271_MAGIC_VALUE) {
            revert InvalidSignature(attester);
        }
    }

    function _recoverSigner(bytes32 digest, bytes calldata signature)
        private
        pure
        returns (address signer)
    {
        bytes32 r;
        bytes32 s;
        uint8 v;

        if (signature.length == 65) {
            // slither-disable-next-line assembly
            assembly ("memory-safe") {
                // Read r, s, and v directly from calldata without copying the signature.
                r := calldataload(signature.offset)
                s := calldataload(add(signature.offset, 0x20))
                v := byte(0, calldataload(add(signature.offset, 0x40)))
            }
        } else if (signature.length == 64) {
            bytes32 vs;
            // slither-disable-next-line assembly
            assembly ("memory-safe") {
                // Read the EIP-2098 r and vs words directly from calldata.
                r := calldataload(signature.offset)
                vs := calldataload(add(signature.offset, 0x20))
            }
            s = vs & EIP2098_S_MASK;
            v = uint8((uint256(vs) >> 255) + 27);
        } else {
            revert InvalidSignatureLength(signature.length);
        }

        if (v < 27) {
            v += 27;
        }

        if (v != 27 && v != 28) {
            return address(0);
        }

        if (uint256(s) > SECP256K1_HALF_ORDER) {
            return address(0);
        }

        // ecrecover returns address(0) on invalid input; the caller compares it to attester.
        signer = ecrecover(digest, v, r, s);
    }
}
