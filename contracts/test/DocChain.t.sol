// SPDX-License-Identifier: CC0-1.0
pragma solidity 0.8.35;

import { DocChain } from "../src/DocChain.sol";

interface Vm {
    function addr(uint256 privateKey) external returns (address);
    function expectEmit(
        bool checkTopic1,
        bool checkTopic2,
        bool checkTopic3,
        bool checkData,
        address emitter
    ) external;
    function expectRevert(bytes4 selector) external;
    function expectRevert(bytes calldata revertData) external;
    function sign(uint256 privateKey, bytes32 digest)
        external
        returns (uint8 v, bytes32 r, bytes32 s);
    function assume(bool condition) external;
    function chainId(uint256 newChainId) external;
    function prank(address msgSender) external;
    function warp(uint256 newTimestamp) external;
}

contract Mock1271Wallet {
    bytes4 private constant MAGIC_VALUE = 0x1626ba7e;

    bytes32 private approvedDigest;
    bytes32 private approvedSignatureHash;

    function approve(bytes32 digest, bytes memory signature) external {
        approvedDigest = digest;
        approvedSignatureHash = keccak256(signature);
    }

    function isValidSignature(bytes32 digest, bytes memory signature)
        external
        view
        returns (bytes4)
    {
        if (digest == approvedDigest && keccak256(signature) == approvedSignatureHash) {
            return MAGIC_VALUE;
        }

        return 0xffffffff;
    }
}

contract Reverting1271Wallet {
    function isValidSignature(bytes32, bytes memory) external pure returns (bytes4) {
        revert("invalid");
    }
}

contract ShortReturn1271Wallet {
    fallback() external {
        assembly ("memory-safe") {
            mstore(0x00, shl(224, 0x1626ba7e))
            return(0x00, 0x03)
        }
    }
}

contract DocChainTest {
    Vm private constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    uint256 private constant ATTESTER_PRIVATE_KEY = 0xA11CE;
    uint256 private constant OTHER_PRIVATE_KEY = 0xB0B;
    uint256 private constant SECP256K1_HALF_ORDER =
        0x7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0;
    bytes32 private constant DOC_CHAIN_ID = keccak256("https://om.pub/rso/docchain/v1");
    bytes32 private constant CONTENT_HASH = keccak256("canonical doc bytes");
    address private constant FIXTURE_VERIFYING_CONTRACT =
        0x000000000000000000000000000000000000D0c0;
    address private constant FIXTURE_ATTESTER = 0xe05fcC23807536bEe418f142D19fa0d21BB0cfF7;
    uint256 private constant FIXTURE_CHAIN_ID = 11_155_111;
    uint256 private constant FIXTURE_DEADLINE = 1_775_755_200;
    bytes32 private constant FIXTURE_DOC_CHAIN_ID =
        0xc083016c1c5370c329ecfaf3806d21a371a97e1d6d3cf977535916d5384e103e;
    uint64 private constant FIXTURE_DOC_REF = 202_605_060_000;
    bytes32 private constant FIXTURE_CONTENT_HASH =
        0xa8b7b5d544dfb935fe43e68e005f5ed61e5e31b69b5e88ce59e1e2d70ae50633;
    bytes32 private constant FIXTURE_DOC_BLOCK_TYPEHASH =
        0xb84212102d711af6fc7ae9fa3e37753befb8b25762a552631b0e9ff9e8d07894;
    bytes32 private constant FIXTURE_DOC_ATTESTATION_TYPEHASH =
        0x9c6b294d547b9e3462d84b736f8bd9d348daf7e68d85d506b624545d4987e5db;
    bytes32 private constant FIXTURE_DOC_BLOCK_HASH =
        0x2de60e9c0d76f33ac0d134357c3a6dcd72f356eda91c328b529fb5d9e5a38305;
    bytes32 private constant FIXTURE_URI_HASH =
        0xa2896eabd7f3b2830f5326ebd6c8b8942aeb432a05603978a1d01314849b1bb6;
    bytes32 private constant FIXTURE_ATTESTATION_HASH =
        0x1ccdc608310432526732e9c6e77e9d228aaa4725125cbd33b677a0ecd57770f8;
    bytes32 private constant FIXTURE_ATTESTATION_KEY =
        0x24d61703cdf0b5c0bf0bfb3c691f22a57bf2a227c484ddbd50402e4cd9248643;
    bytes32 private constant FIXTURE_DOMAIN_SEPARATOR =
        0xd39852038b61784cd59f43d990ddae31d807b9ec84a9003fc444c8136101288c;
    bytes32 private constant FIXTURE_ATTESTATION_DIGEST =
        0xd32a0e66e3ab1d40c62b1d0f353dc3afd9538a732b83bcd98c350f4c52eba677;
    bytes32 private constant FIXTURE_SIGNATURE_R =
        0x20b91bbe414fe1b06e8839f47876d332067ce9b411f64b3257a0e203d4903d04;
    bytes32 private constant FIXTURE_SIGNATURE_S =
        0x64e19d39e0e719bb0140965284b8077a2beb05cda7e02235df193c05d2fcc967;
    uint8 private constant FIXTURE_SIGNATURE_V = 28;

    DocChain private chain;
    address private attester;

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

    function setUp() public {
        vm.warp(1_775_668_800);
        chain = new DocChain();
        attester = vm.addr(ATTESTER_PRIVATE_KEY);
    }

    function testAttestsEoaAndEmitsData() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);

        bytes32 blockHash = chain.hashDocBlock(attestation.docBlock);
        bytes32 uriHash = keccak256(bytes(attestation.uri));
        bytes32 key = chain.attestationKey(attestation.attester, attestation.docBlock, uriHash);

        vm.expectEmit(true, true, true, true, address(chain));
        emit DocAttested(
            attestation.docBlock.docChainId,
            attestation.attester,
            attestation.docBlock.docRef,
            address(this),
            attestation.docBlock.parentHash,
            blockHash,
            attestation.docBlock.contentHash,
            uriHash,
            attestation.uri
        );

        (bytes32 returnedBlockHash, bytes32 returnedUriHash, bytes32 returnedKey) =
            chain.attestDoc(attestation, signature);

        assertEq(returnedBlockHash, blockHash);
        assertEq(returnedUriHash, uriHash);
        assertEq(returnedKey, key);
        assertTrue(chain.attested(key));
    }

    function testAcceptsEip2098CompactSignature() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        bytes memory signature = _signCompact(ATTESTER_PRIVATE_KEY, attestation);

        (,, bytes32 key) = chain.attestDoc(attestation, signature);

        assertTrue(chain.attested(key));
    }

    function testAcceptsZeroOneVSignature() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);
        signature[64] = bytes1(uint8(signature[64]) - 27);

        (,, bytes32 key) = chain.attestDoc(attestation, signature);

        assertTrue(chain.attested(key));
    }

    function testAcceptsDeadlineEqualToBlockTimestamp() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        attestation.deadline = block.timestamp;
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);

        (,, bytes32 key) = chain.attestDoc(attestation, signature);

        assertTrue(chain.attested(key));
    }

    function testAcceptsEmptyUri() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        attestation.uri = "";
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);

        (bytes32 blockHash, bytes32 uriHash, bytes32 key) = chain.attestDoc(attestation, signature);

        assertEq(blockHash, chain.hashDocBlock(attestation.docBlock));
        assertEq(uriHash, keccak256(""));
        assertTrue(chain.attested(key));
    }

    function testAcceptsMaxLengthUri() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        attestation.uri = string(new bytes(chain.MAX_URI_BYTES()));
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);

        (,, bytes32 key) = chain.attestDoc(attestation, signature);

        assertTrue(chain.attested(key));
    }

    function testAllowsSameBlockWithDifferentUri() public {
        DocChain.DocAttestation memory first = _attestation(attester);
        bytes memory firstSignature = _sign(ATTESTER_PRIVATE_KEY, first);
        (,, bytes32 firstKey) = chain.attestDoc(first, firstSignature);

        DocChain.DocAttestation memory second = _attestation(attester);
        second.uri = "ar://doc-chain-attestation";
        bytes memory secondSignature = _sign(ATTESTER_PRIVATE_KEY, second);
        (,, bytes32 secondKey) = chain.attestDoc(second, secondSignature);

        assertTrue(chain.attested(firstKey));
        assertTrue(chain.attested(secondKey));
        assertNotEq(firstKey, secondKey);
    }

    function testRelayerIsRecordedAsSubmitter() public {
        address relayer = address(0xBEEF);
        DocChain.DocAttestation memory attestation = _attestation(attester);
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);
        bytes32 blockHash = chain.hashDocBlock(attestation.docBlock);
        bytes32 uriHash = keccak256(bytes(attestation.uri));

        vm.expectEmit(true, true, true, true, address(chain));
        emit DocAttested(
            attestation.docBlock.docChainId,
            attestation.attester,
            attestation.docBlock.docRef,
            relayer,
            attestation.docBlock.parentHash,
            blockHash,
            attestation.docBlock.contentHash,
            uriHash,
            attestation.uri
        );

        vm.prank(relayer);
        chain.attestDoc(attestation, signature);
    }

    function testSupportsEip1271ContractWallets() public {
        Mock1271Wallet wallet = new Mock1271Wallet();
        DocChain.DocAttestation memory attestation = _attestation(address(wallet));
        bytes memory signature = hex"c0ffee";

        wallet.approve(chain.attestationDigest(attestation), signature);
        (,, bytes32 key) = chain.attestDoc(attestation, signature);

        assertTrue(chain.attested(key));
    }

    function testRejectsInvalidEip1271Signature() public {
        Mock1271Wallet wallet = new Mock1271Wallet();
        DocChain.DocAttestation memory attestation = _attestation(address(wallet));

        vm.expectRevert(abi.encodeWithSelector(DocChain.InvalidSignature.selector, address(wallet)));
        chain.attestDoc(attestation, bytes("bad-sig"));
    }

    function testRejectsRevertingEip1271Wallet() public {
        Reverting1271Wallet wallet = new Reverting1271Wallet();
        DocChain.DocAttestation memory attestation = _attestation(address(wallet));

        vm.expectRevert(abi.encodeWithSelector(DocChain.InvalidSignature.selector, address(wallet)));
        chain.attestDoc(attestation, hex"c0ffee");
    }

    function testRejectsShortEip1271Return() public {
        ShortReturn1271Wallet wallet = new ShortReturn1271Wallet();
        DocChain.DocAttestation memory attestation = _attestation(address(wallet));

        vm.expectRevert(abi.encodeWithSelector(DocChain.InvalidSignature.selector, address(wallet)));
        chain.attestDoc(attestation, hex"c0ffee");
    }

    function testRejectsDuplicateAttestation() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);

        chain.attestDoc(attestation, signature);

        bytes32 uriHash = keccak256(bytes(attestation.uri));
        bytes32 key = chain.attestationKey(attestation.attester, attestation.docBlock, uriHash);

        vm.expectRevert(abi.encodeWithSelector(DocChain.DuplicateAttestation.selector, key));
        chain.attestDoc(attestation, signature);
    }

    function testRejectsExpiredDeadline() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        attestation.deadline = block.timestamp - 1;
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);

        vm.expectRevert(
            abi.encodeWithSelector(
                DocChain.DeadlineExpired.selector, attestation.deadline, block.timestamp
            )
        );
        chain.attestDoc(attestation, signature);
    }

    function testRejectsUriLongerThanCap() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        attestation.uri = string(new bytes(chain.MAX_URI_BYTES() + 1));

        vm.expectRevert(
            abi.encodeWithSelector(
                DocChain.UriTooLong.selector, bytes(attestation.uri).length, chain.MAX_URI_BYTES()
            )
        );
        chain.attestDoc(attestation, "");
    }

    function testRejectsWrongEoaSigner() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        bytes memory signature = _sign(OTHER_PRIVATE_KEY, attestation);

        vm.expectRevert(abi.encodeWithSelector(DocChain.InvalidSignature.selector, attester));
        chain.attestDoc(attestation, signature);
    }

    function testRejectsMalformedEoaSignatureLength() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);

        vm.expectRevert(abi.encodeWithSelector(DocChain.InvalidSignatureLength.selector, 2));
        chain.attestDoc(attestation, hex"1234");
    }

    function testRejectsHighSSignature() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        bytes memory signature =
            abi.encodePacked(bytes32(uint256(1)), bytes32(SECP256K1_HALF_ORDER + 1), uint8(27));

        vm.expectRevert(abi.encodeWithSelector(DocChain.InvalidSignature.selector, attester));
        chain.attestDoc(attestation, signature);
    }

    function testRejectsCompactHighSSignature() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        bytes memory signature =
            abi.encodePacked(bytes32(uint256(1)), bytes32(SECP256K1_HALF_ORDER + 1));

        vm.expectRevert(abi.encodeWithSelector(DocChain.InvalidSignature.selector, attester));
        chain.attestDoc(attestation, signature);
    }

    function testRejectsCompactHighSSignatureWithVFlag() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        bytes32 vs = bytes32((uint256(1) << 255) | (SECP256K1_HALF_ORDER + 1));
        bytes memory signature = abi.encodePacked(bytes32(uint256(1)), vs);

        vm.expectRevert(abi.encodeWithSelector(DocChain.InvalidSignature.selector, attester));
        chain.attestDoc(attestation, signature);
    }

    function testRejectsInvalidVSignature() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        bytes memory signature =
            abi.encodePacked(bytes32(uint256(1)), bytes32(uint256(1)), uint8(29));

        vm.expectRevert(abi.encodeWithSelector(DocChain.InvalidSignature.selector, attester));
        chain.attestDoc(attestation, signature);
    }

    function testRejectsZeroAttester() public {
        DocChain.DocAttestation memory attestation = _attestation(address(0));

        vm.expectRevert(DocChain.InvalidAttester.selector);
        chain.attestDoc(attestation, "");
    }

    function testRejectsSignatureForDifferentContractDomain() public {
        DocChain otherChain = new DocChain();
        DocChain.DocAttestation memory attestation = _attestation(attester);
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);

        vm.expectRevert(abi.encodeWithSelector(DocChain.InvalidSignature.selector, attester));
        otherChain.attestDoc(attestation, signature);
    }

    function testRejectsSignatureAfterChainIdChange() public {
        DocChain.DocAttestation memory attestation = _attestation(attester);
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);

        vm.chainId(FIXTURE_CHAIN_ID);

        vm.expectRevert(abi.encodeWithSelector(DocChain.InvalidSignature.selector, attester));
        chain.attestDoc(attestation, signature);
    }

    function testDomainSeparatorIncludesChainAndContract() public view {
        bytes32 expected = keccak256(
            abi.encode(
                chain.EIP712_DOMAIN_TYPEHASH(),
                keccak256(bytes(chain.NAME())),
                keccak256(bytes(chain.VERSION())),
                block.chainid,
                address(chain)
            )
        );

        assertEq(chain.DOMAIN_SEPARATOR(), expected);
    }

    function testFixtureGoldenVectorMatchesContractHashing() public view {
        DocChain.DocBlock memory docBlock = DocChain.DocBlock({
            docChainId: FIXTURE_DOC_CHAIN_ID,
            docRef: FIXTURE_DOC_REF,
            parentHash: bytes32(0),
            contentHash: FIXTURE_CONTENT_HASH
        });
        DocChain.DocAttestation memory attestation = DocChain.DocAttestation({
            attester: FIXTURE_ATTESTER,
            docBlock: docBlock,
            uri: "ipfs://bafybeidocchainattestation",
            deadline: FIXTURE_DEADLINE
        });

        assertEq(
            chain.EIP712_DOMAIN_TYPEHASH(),
            0x8b73c3c69bb8fe3d512ecc4cf759cc79239f7b179b0ffacaa9a75d522b39400f
        );
        assertEq(chain.DOC_BLOCK_TYPEHASH(), FIXTURE_DOC_BLOCK_TYPEHASH);
        assertEq(chain.DOC_ATTESTATION_TYPEHASH(), FIXTURE_DOC_ATTESTATION_TYPEHASH);
        assertEq(chain.hashDocBlock(docBlock), FIXTURE_DOC_BLOCK_HASH);
        assertEq(keccak256(bytes(attestation.uri)), FIXTURE_URI_HASH);
        assertEq(chain.hashAttestation(attestation), FIXTURE_ATTESTATION_HASH);
        assertEq(
            chain.attestationKey(FIXTURE_ATTESTER, docBlock, FIXTURE_URI_HASH),
            FIXTURE_ATTESTATION_KEY
        );

        bytes32 domainSeparator = keccak256(
            abi.encode(
                chain.EIP712_DOMAIN_TYPEHASH(),
                keccak256(bytes(chain.NAME())),
                keccak256(bytes(chain.VERSION())),
                FIXTURE_CHAIN_ID,
                FIXTURE_VERIFYING_CONTRACT
            )
        );
        bytes32 digest = keccak256(
            abi.encodePacked("\x19\x01", domainSeparator, chain.hashAttestation(attestation))
        );

        assertEq(domainSeparator, FIXTURE_DOMAIN_SEPARATOR);
        assertEq(digest, FIXTURE_ATTESTATION_DIGEST);
        assertEq(
            ecrecover(digest, FIXTURE_SIGNATURE_V, FIXTURE_SIGNATURE_R, FIXTURE_SIGNATURE_S),
            FIXTURE_ATTESTER
        );
    }

    function testDomainSeparatorRecomputesAfterChainIdChange() public {
        vm.chainId(FIXTURE_CHAIN_ID);

        bytes32 expected = keccak256(
            abi.encode(
                chain.EIP712_DOMAIN_TYPEHASH(),
                keccak256(bytes(chain.NAME())),
                keccak256(bytes(chain.VERSION())),
                block.chainid,
                address(chain)
            )
        );

        assertEq(chain.DOMAIN_SEPARATOR(), expected);
    }

    function testFuzzHashDocBlockMatchesTypedEncoding(
        bytes32 docChainId,
        uint64 docRef,
        bytes32 parentHash,
        bytes32 contentHash
    ) public view {
        DocChain.DocBlock memory docBlock = DocChain.DocBlock({
            docChainId: docChainId, docRef: docRef, parentHash: parentHash, contentHash: contentHash
        });

        bytes32 expected = keccak256(
            abi.encode(chain.DOC_BLOCK_TYPEHASH(), docChainId, docRef, parentHash, contentHash)
        );

        assertEq(chain.hashDocBlock(docBlock), expected);
    }

    function testFuzzHashAttestationMatchesTypedEncoding(
        address signer,
        bytes32 docChainId,
        uint64 docRef,
        bytes32 parentHash,
        bytes32 contentHash,
        bytes memory uriBytes,
        uint256 deadline
    ) public {
        vm.assume(uriBytes.length <= 512);
        string memory uri = string(uriBytes);
        DocChain.DocBlock memory docBlock = DocChain.DocBlock({
            docChainId: docChainId, docRef: docRef, parentHash: parentHash, contentHash: contentHash
        });
        DocChain.DocAttestation memory attestation = DocChain.DocAttestation({
            attester: signer, docBlock: docBlock, uri: uri, deadline: deadline
        });

        bytes32 expected = keccak256(
            abi.encode(
                chain.DOC_ATTESTATION_TYPEHASH(),
                signer,
                chain.hashDocBlock(docBlock),
                keccak256(bytes(uri)),
                deadline
            )
        );

        assertEq(chain.hashAttestation(attestation), expected);
    }

    function testFuzzAttestationKeyMatchesTypedEncoding(
        address signer,
        bytes32 docChainId,
        uint64 docRef,
        bytes32 parentHash,
        bytes32 contentHash,
        bytes32 uriHash
    ) public view {
        DocChain.DocBlock memory docBlock = DocChain.DocBlock({
            docChainId: docChainId, docRef: docRef, parentHash: parentHash, contentHash: contentHash
        });

        bytes32 expected =
            keccak256(abi.encode(signer, docChainId, docRef, parentHash, contentHash, uriHash));

        assertEq(chain.attestationKey(signer, docBlock, uriHash), expected);
    }

    function testFuzzAttestsEoa(
        bytes32 docChainId,
        uint64 docRef,
        bytes32 parentHash,
        bytes32 contentHash,
        bytes memory uriBytes,
        uint256 deadlineOffset
    ) public {
        vm.assume(uriBytes.length <= 512);
        DocChain.DocAttestation memory attestation = DocChain.DocAttestation({
            attester: attester,
            docBlock: DocChain.DocBlock({
                docChainId: docChainId,
                docRef: docRef,
                parentHash: parentHash,
                contentHash: contentHash
            }),
            uri: string(uriBytes),
            deadline: block.timestamp + (deadlineOffset % 365 days)
        });
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);

        (bytes32 blockHash, bytes32 uriHash, bytes32 key) = chain.attestDoc(attestation, signature);

        assertEq(blockHash, chain.hashDocBlock(attestation.docBlock));
        assertEq(uriHash, keccak256(bytes(attestation.uri)));
        assertEq(key, chain.attestationKey(attester, attestation.docBlock, uriHash));
        assertTrue(chain.attested(key));
    }

    function _attestation(address signer) private view returns (DocChain.DocAttestation memory) {
        return DocChain.DocAttestation({
            attester: signer,
            docBlock: DocChain.DocBlock({
                docChainId: DOC_CHAIN_ID,
                docRef: 202605060000,
                parentHash: bytes32(0),
                contentHash: CONTENT_HASH
            }),
            uri: "ipfs://bafybeidocchainattestation",
            deadline: block.timestamp + 1 days
        });
    }

    function _sign(uint256 privateKey, DocChain.DocAttestation memory attestation)
        private
        returns (bytes memory)
    {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(privateKey, chain.attestationDigest(attestation));
        return abi.encodePacked(r, s, v);
    }

    function _signCompact(uint256 privateKey, DocChain.DocAttestation memory attestation)
        private
        returns (bytes memory)
    {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(privateKey, chain.attestationDigest(attestation));
        bytes32 vs = v == 28 ? bytes32(uint256(s) | (uint256(1) << 255)) : s;
        return abi.encodePacked(r, vs);
    }

    function assertTrue(bool value) private pure {
        if (!value) {
            revert("assert true failed");
        }
    }

    function assertEq(bytes32 actual, bytes32 expected) private pure {
        if (actual != expected) {
            revert("assert bytes32 eq failed");
        }
    }

    function assertEq(address actual, address expected) private pure {
        if (actual != expected) {
            revert("assert address eq failed");
        }
    }

    function assertNotEq(bytes32 actual, bytes32 expected) private pure {
        if (actual == expected) {
            revert("assert bytes32 not eq failed");
        }
    }
}
