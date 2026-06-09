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
    bytes32 private constant DOC_CHAIN_ID = keccak256("https://om.pub/rso/doc-chain/v1");
    bytes32 private constant CONTENT_HASH = keccak256("canonical doc bytes");
    address private constant FIXTURE_VERIFYING_CONTRACT =
        0x000000000000000000000000000000000000D0c0;
    address private constant FIXTURE_ATTESTER = 0xe05fcC23807536bEe418f142D19fa0d21BB0cfF7;
    address private constant FIXTURE_ON_BEHALF_OF = 0x0000000000000000000000000000000000006529;
    uint256 private constant FIXTURE_CHAIN_ID = 11_155_111;
    uint256 private constant FIXTURE_DEADLINE = 1_775_755_200;
    bytes32 private constant FIXTURE_DOC_CHAIN_ID =
        0x8621c2851714436d60da45cf0e11253114a4f2002f73ddc159b4dc88fea5611d;
    uint64 private constant FIXTURE_DOC_REF = 20_260_506_000_000;
    bytes32 private constant FIXTURE_CONTENT_HASH =
        0xa8b7b5d544dfb935fe43e68e005f5ed61e5e31b69b5e88ce59e1e2d70ae50633;
    bytes32 private constant FIXTURE_DOC_BLOCK_TYPEHASH =
        0xb84212102d711af6fc7ae9fa3e37753befb8b25762a552631b0e9ff9e8d07894;
    bytes32 private constant FIXTURE_DOC_ATTESTATION_TYPEHASH =
        0x3cc0802d08c3f09619971b7d94c27c3cf2bd6da0582b399b6ab9259e8c75de6d;
    bytes32 private constant FIXTURE_DOC_BLOCK_HASH =
        0x4be140a3a0f69195baf0a96bfd1df201163e286cf1faf504697500e9abbd6a3c;
    bytes32 private constant FIXTURE_URI_HASH =
        0xa2896eabd7f3b2830f5326ebd6c8b8942aeb432a05603978a1d01314849b1bb6;
    bytes32 private constant FIXTURE_ATTESTATION_HASH =
        0xbed0ca9144965182ee3de2975fb0bdcd4ca14df1f8ef10f2521e5af86d38fecf;
    bytes32 private constant FIXTURE_ATTESTATION_KEY =
        0x13ef27af2426c2dcf9407382a04bbfd9fabdbbd8ad406166410abf921377d3a5;
    bytes32 private constant FIXTURE_DOMAIN_SEPARATOR =
        0xd39852038b61784cd59f43d990ddae31d807b9ec84a9003fc444c8136101288c;
    bytes32 private constant FIXTURE_ATTESTATION_DIGEST =
        0x960cea4a8155a08f29795a6ad7ca5d81f7d793fcbfdc95db12a6d889645e5697;
    bytes32 private constant FIXTURE_SIGNATURE_R =
        0x752b9c40dc0893ae03a0edd4cdf344d2a890df85703b36d23795bdcb1bead15d;
    bytes32 private constant FIXTURE_SIGNATURE_S =
        0x6bda2861c1df7660116b80752be9117be5f30fc5a26585517fa608dde6218541;
    uint8 private constant FIXTURE_SIGNATURE_V = 27;

    DocChain private chain;
    address private attester;

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
        bytes32 key = chain.attestationKey(
            attestation.attester, attestation.onBehalfOf, attestation.docBlock, uriHash
        );

        vm.expectEmit(true, true, true, true, address(chain));
        emit DocAttested(
            attestation.docBlock.docChainId,
            attestation.attester,
            attestation.docBlock.docRef,
            attestation.onBehalfOf,
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

    function testAllowsSameBlockWithDifferentOnBehalfOf() public {
        DocChain.DocAttestation memory first = _attestationFor(attester, address(0x1234));
        bytes memory firstSignature = _sign(ATTESTER_PRIVATE_KEY, first);
        (,, bytes32 firstKey) = chain.attestDoc(first, firstSignature);

        DocChain.DocAttestation memory second = _attestationFor(attester, address(0x5678));
        bytes memory secondSignature = _sign(ATTESTER_PRIVATE_KEY, second);
        (,, bytes32 secondKey) = chain.attestDoc(second, secondSignature);

        assertTrue(chain.attested(firstKey));
        assertTrue(chain.attested(secondKey));
        assertNotEq(firstKey, secondKey);
    }

    function testAttestsOnBehalfOfAndEmitsData() public {
        DocChain.DocAttestation memory attestation = _attestationFor(attester, address(0x6529));
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);
        bytes32 blockHash = chain.hashDocBlock(attestation.docBlock);
        bytes32 uriHash = keccak256(bytes(attestation.uri));

        vm.expectEmit(true, true, true, true, address(chain));
        emit DocAttested(
            attestation.docBlock.docChainId,
            attestation.attester,
            attestation.docBlock.docRef,
            attestation.onBehalfOf,
            address(this),
            attestation.docBlock.parentHash,
            blockHash,
            attestation.docBlock.contentHash,
            uriHash,
            attestation.uri
        );

        (,, bytes32 key) = chain.attestDoc(attestation, signature);

        assertTrue(chain.attested(key));
    }

    function testOnBehalfOfIsSigned() public {
        DocChain.DocAttestation memory attestation = _attestationFor(attester, address(0x1234));
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);
        attestation.onBehalfOf = address(0x5678);

        vm.expectRevert(abi.encodeWithSelector(DocChain.InvalidSignature.selector, attester));
        chain.attestDoc(attestation, signature);
    }

    function testAttestationKeyIncludesOnBehalfOf() public view {
        DocChain.DocAttestation memory attestation = _attestationFor(attester, address(0x1234));
        bytes32 uriHash = keccak256(bytes(attestation.uri));

        bytes32 firstKey = chain.attestationKey(
            attestation.attester, attestation.onBehalfOf, attestation.docBlock, uriHash
        );
        bytes32 secondKey = chain.attestationKey(
            attestation.attester, address(0x5678), attestation.docBlock, uriHash
        );

        assertNotEq(firstKey, secondKey);
    }

    function testCourierIsRecordedAsSubmitter() public {
        address courier = address(0xBEEF);
        DocChain.DocAttestation memory attestation = _attestation(attester);
        bytes memory signature = _sign(ATTESTER_PRIVATE_KEY, attestation);
        bytes32 blockHash = chain.hashDocBlock(attestation.docBlock);
        bytes32 uriHash = keccak256(bytes(attestation.uri));

        vm.expectEmit(true, true, true, true, address(chain));
        emit DocAttested(
            attestation.docBlock.docChainId,
            attestation.attester,
            attestation.docBlock.docRef,
            attestation.onBehalfOf,
            courier,
            attestation.docBlock.parentHash,
            blockHash,
            attestation.docBlock.contentHash,
            uriHash,
            attestation.uri
        );

        vm.prank(courier);
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
        bytes32 key = chain.attestationKey(
            attestation.attester, attestation.onBehalfOf, attestation.docBlock, uriHash
        );

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
            onBehalfOf: FIXTURE_ON_BEHALF_OF,
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
            chain.attestationKey(
                FIXTURE_ATTESTER, FIXTURE_ON_BEHALF_OF, docBlock, FIXTURE_URI_HASH
            ),
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
        address onBehalfOf,
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
            attester: signer,
            onBehalfOf: onBehalfOf,
            docBlock: docBlock,
            uri: uri,
            deadline: deadline
        });

        bytes32 expected = keccak256(
            abi.encode(
                chain.DOC_ATTESTATION_TYPEHASH(),
                signer,
                onBehalfOf,
                chain.hashDocBlock(docBlock),
                keccak256(bytes(uri)),
                deadline
            )
        );

        assertEq(chain.hashAttestation(attestation), expected);
    }

    function testFuzzAttestationKeyMatchesTypedEncoding(
        address signer,
        address onBehalfOf,
        bytes32 docChainId,
        uint64 docRef,
        bytes32 parentHash,
        bytes32 contentHash,
        bytes32 uriHash
    ) public view {
        DocChain.DocBlock memory docBlock = DocChain.DocBlock({
            docChainId: docChainId, docRef: docRef, parentHash: parentHash, contentHash: contentHash
        });

        bytes32 expected = keccak256(
            abi.encode(signer, onBehalfOf, docChainId, docRef, parentHash, contentHash, uriHash)
        );

        assertEq(chain.attestationKey(signer, onBehalfOf, docBlock, uriHash), expected);
    }

    function testFuzzAttestsEoa(
        address onBehalfOf,
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
            onBehalfOf: onBehalfOf,
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
        assertEq(
            key,
            chain.attestationKey(attester, attestation.onBehalfOf, attestation.docBlock, uriHash)
        );
        assertTrue(chain.attested(key));
    }

    function testBatchAttestsChainedDays() public {
        uint256 dayCount = 5;
        (DocChain.DocAttestation[] memory attestations, bytes[] memory signatures) =
            _chainedBatch(ATTESTER_PRIVATE_KEY, 20260420000000, dayCount);

        (uint256 storedCount, uint256 skippedCount) = chain.attestBatch(attestations, signatures);

        assertEq(storedCount, dayCount);
        assertEq(skippedCount, 0);
        for (uint256 i = 0; i < dayCount; i++) {
            bytes32 uriHash = keccak256(bytes(attestations[i].uri));
            bytes32 key = chain.attestationKey(
                attestations[i].attester,
                attestations[i].onBehalfOf,
                attestations[i].docBlock,
                uriHash
            );
            assertTrue(chain.attested(key));
        }
    }

    function testBatchEmitsPerItemEvents() public {
        (DocChain.DocAttestation[] memory attestations, bytes[] memory signatures) =
            _chainedBatch(ATTESTER_PRIVATE_KEY, 20260420000000, 2);

        for (uint256 i = 0; i < attestations.length; i++) {
            vm.expectEmit(true, true, true, true, address(chain));
            emit DocAttested(
                attestations[i].docBlock.docChainId,
                attestations[i].attester,
                attestations[i].docBlock.docRef,
                attestations[i].onBehalfOf,
                address(this),
                attestations[i].docBlock.parentHash,
                chain.hashDocBlock(attestations[i].docBlock),
                attestations[i].docBlock.contentHash,
                keccak256(bytes(attestations[i].uri)),
                attestations[i].uri
            );
        }

        chain.attestBatch(attestations, signatures);
    }

    function testBatchMixedAttesters() public {
        DocChain.DocAttestation[] memory attestations = new DocChain.DocAttestation[](2);
        bytes[] memory signatures = new bytes[](2);
        attestations[0] = _attestation(attester);
        signatures[0] = _sign(ATTESTER_PRIVATE_KEY, attestations[0]);
        attestations[1] = _attestation(vm.addr(OTHER_PRIVATE_KEY));
        signatures[1] = _sign(OTHER_PRIVATE_KEY, attestations[1]);

        (uint256 storedCount, uint256 skippedCount) = chain.attestBatch(attestations, signatures);

        assertEq(storedCount, 2);
        assertEq(skippedCount, 0);
    }

    function testBatchMixedSignatureFormats() public {
        Mock1271Wallet wallet = new Mock1271Wallet();
        DocChain.DocAttestation[] memory attestations = new DocChain.DocAttestation[](3);
        bytes[] memory signatures = new bytes[](3);

        attestations[0] = _attestation(attester);
        signatures[0] = _sign(ATTESTER_PRIVATE_KEY, attestations[0]);
        attestations[1] = _attestation(vm.addr(OTHER_PRIVATE_KEY));
        signatures[1] = _signCompact(OTHER_PRIVATE_KEY, attestations[1]);
        attestations[2] = _attestation(address(wallet));
        signatures[2] = hex"c0ffee";
        wallet.approve(chain.attestationDigest(attestations[2]), signatures[2]);

        (uint256 storedCount, uint256 skippedCount) = chain.attestBatch(attestations, signatures);

        assertEq(storedCount, 3);
        assertEq(skippedCount, 0);
    }

    function testBatchSkipsDuplicateAlreadyOnChain() public {
        (DocChain.DocAttestation[] memory attestations, bytes[] memory signatures) =
            _chainedBatch(ATTESTER_PRIVATE_KEY, 20260420000000, 3);
        chain.attestDoc(attestations[0], signatures[0]);

        (uint256 storedCount, uint256 skippedCount) = chain.attestBatch(attestations, signatures);

        assertEq(storedCount, 2);
        assertEq(skippedCount, 1);
    }

    function testBatchIdempotentFullResubmission() public {
        (DocChain.DocAttestation[] memory attestations, bytes[] memory signatures) =
            _chainedBatch(ATTESTER_PRIVATE_KEY, 20260420000000, 4);

        (uint256 firstStored,) = chain.attestBatch(attestations, signatures);
        (uint256 secondStored, uint256 secondSkipped) = chain.attestBatch(attestations, signatures);

        assertEq(firstStored, 4);
        assertEq(secondStored, 0);
        assertEq(secondSkipped, 4);
    }

    function testBatchSkipsExpiredDuplicate() public {
        // An already-recorded item whose deadline has since passed must skip, not
        // revert: resubmitting a partially landed batch stays safe at any later time.
        DocChain.DocAttestation[] memory attestations = new DocChain.DocAttestation[](2);
        bytes[] memory signatures = new bytes[](2);
        attestations[0] = _attestation(attester);
        signatures[0] = _sign(ATTESTER_PRIVATE_KEY, attestations[0]);
        chain.attestDoc(attestations[0], signatures[0]);

        vm.warp(attestations[0].deadline + 1);

        attestations[1] = _attestation(attester);
        attestations[1].docBlock.docRef = 20260421000000;
        attestations[1].deadline = block.timestamp + 1 days;
        signatures[1] = _sign(ATTESTER_PRIVATE_KEY, attestations[1]);

        (uint256 storedCount, uint256 skippedCount) = chain.attestBatch(attestations, signatures);

        assertEq(storedCount, 1);
        assertEq(skippedCount, 1);
    }

    function testBatchSkipsDuplicateWithinBatch() public {
        DocChain.DocAttestation[] memory attestations = new DocChain.DocAttestation[](2);
        bytes[] memory signatures = new bytes[](2);
        attestations[0] = _attestation(attester);
        signatures[0] = _sign(ATTESTER_PRIVATE_KEY, attestations[0]);
        attestations[1] = attestations[0];
        signatures[1] = signatures[0];

        (uint256 storedCount, uint256 skippedCount) = chain.attestBatch(attestations, signatures);

        assertEq(storedCount, 1);
        assertEq(skippedCount, 1);
    }

    function testBatchRevertsOnInvalidSignatureAndStoresNothing() public {
        (DocChain.DocAttestation[] memory attestations, bytes[] memory signatures) =
            _chainedBatch(ATTESTER_PRIVATE_KEY, 20260420000000, 3);
        signatures[1] = _sign(OTHER_PRIVATE_KEY, attestations[1]);
        bytes32 firstKey = chain.attestationKey(
            attestations[0].attester,
            attestations[0].onBehalfOf,
            attestations[0].docBlock,
            keccak256(bytes(attestations[0].uri))
        );

        vm.expectRevert(abi.encodeWithSelector(DocChain.InvalidSignature.selector, attester));
        chain.attestBatch(attestations, signatures);

        assertTrue(!chain.attested(firstKey));
    }

    function testBatchRevertsOnExpiredNonDuplicate() public {
        (DocChain.DocAttestation[] memory attestations, bytes[] memory signatures) =
            _chainedBatch(ATTESTER_PRIVATE_KEY, 20260420000000, 2);
        attestations[1].deadline = block.timestamp - 1;
        signatures[1] = _sign(ATTESTER_PRIVATE_KEY, attestations[1]);

        vm.expectRevert(
            abi.encodeWithSelector(
                DocChain.DeadlineExpired.selector, attestations[1].deadline, block.timestamp
            )
        );
        chain.attestBatch(attestations, signatures);
    }

    function testBatchRevertsOnLengthMismatch() public {
        (DocChain.DocAttestation[] memory attestations,) =
            _chainedBatch(ATTESTER_PRIVATE_KEY, 20260420000000, 2);
        bytes[] memory signatures = new bytes[](1);
        signatures[0] = _sign(ATTESTER_PRIVATE_KEY, attestations[0]);

        vm.expectRevert(abi.encodeWithSelector(DocChain.BatchLengthMismatch.selector, 2, 1));
        chain.attestBatch(attestations, signatures);
    }

    function testBatchRevertsOnEmpty() public {
        DocChain.DocAttestation[] memory attestations = new DocChain.DocAttestation[](0);
        bytes[] memory signatures = new bytes[](0);

        vm.expectRevert(DocChain.EmptyBatch.selector);
        chain.attestBatch(attestations, signatures);
    }

    function testBatchRevertsOnZeroAttester() public {
        DocChain.DocAttestation[] memory attestations = new DocChain.DocAttestation[](1);
        bytes[] memory signatures = new bytes[](1);
        attestations[0] = _attestation(address(0));
        signatures[0] = "";

        vm.expectRevert(DocChain.InvalidAttester.selector);
        chain.attestBatch(attestations, signatures);
    }

    function testBatchRevertsOnOverlongUri() public {
        DocChain.DocAttestation[] memory attestations = new DocChain.DocAttestation[](1);
        bytes[] memory signatures = new bytes[](1);
        attestations[0] = _attestation(attester);
        attestations[0].uri = string(new bytes(chain.MAX_URI_BYTES() + 1));
        signatures[0] = "";

        vm.expectRevert(
            abi.encodeWithSelector(
                DocChain.UriTooLong.selector,
                bytes(attestations[0].uri).length,
                chain.MAX_URI_BYTES()
            )
        );
        chain.attestBatch(attestations, signatures);
    }

    function testBatchCourierRecordedAsSubmitter() public {
        address courier = address(0xBEEF);
        (DocChain.DocAttestation[] memory attestations, bytes[] memory signatures) =
            _chainedBatch(ATTESTER_PRIVATE_KEY, 20260420000000, 1);

        vm.expectEmit(true, true, true, true, address(chain));
        emit DocAttested(
            attestations[0].docBlock.docChainId,
            attestations[0].attester,
            attestations[0].docBlock.docRef,
            attestations[0].onBehalfOf,
            courier,
            attestations[0].docBlock.parentHash,
            chain.hashDocBlock(attestations[0].docBlock),
            attestations[0].docBlock.contentHash,
            keccak256(bytes(attestations[0].uri)),
            attestations[0].uri
        );

        vm.prank(courier);
        chain.attestBatch(attestations, signatures);
    }

    function testAttestDocRevertsDuplicateStoredViaBatch() public {
        (DocChain.DocAttestation[] memory attestations, bytes[] memory signatures) =
            _chainedBatch(ATTESTER_PRIVATE_KEY, 20260420000000, 1);
        chain.attestBatch(attestations, signatures);

        bytes32 key = chain.attestationKey(
            attestations[0].attester,
            attestations[0].onBehalfOf,
            attestations[0].docBlock,
            keccak256(bytes(attestations[0].uri))
        );

        vm.expectRevert(abi.encodeWithSelector(DocChain.DuplicateAttestation.selector, key));
        chain.attestDoc(attestations[0], signatures[0]);
    }

    function testBatchFiftyOneDayGenesisReplay() public {
        // The late-join scenario this feature exists for: one node attests every
        // archive day since genesis in a single transaction.
        uint256 dayCount = 51;
        (DocChain.DocAttestation[] memory attestations, bytes[] memory signatures) =
            _chainedBatch(ATTESTER_PRIVATE_KEY, 20260420000000, dayCount);

        uint256 gasBefore = gasleft();
        (uint256 storedCount,) = chain.attestBatch(attestations, signatures);
        uint256 gasUsed = gasBefore - gasleft();

        assertEq(storedCount, dayCount);
        // Keep the full from-genesis batch comfortably inside one block.
        assertTrue(gasUsed < 6_000_000);

        bytes32 lastKey = chain.attestationKey(
            attestations[dayCount - 1].attester,
            attestations[dayCount - 1].onBehalfOf,
            attestations[dayCount - 1].docBlock,
            keccak256(bytes(attestations[dayCount - 1].uri))
        );
        assertTrue(chain.attested(lastKey));
    }

    function testFuzzBatchAttestsEoa(uint8 rawCount, bytes32 contentSeed) public {
        uint256 dayCount = (uint256(rawCount) % 8) + 1;
        DocChain.DocAttestation[] memory attestations = new DocChain.DocAttestation[](dayCount);
        bytes[] memory signatures = new bytes[](dayCount);
        bytes32 parentHash = bytes32(0);

        for (uint256 i = 0; i < dayCount; i++) {
            attestations[i] = _attestation(attester);
            attestations[i].docBlock.docRef = uint64(20260420000000 + i * 1_000_000);
            attestations[i].docBlock.parentHash = parentHash;
            attestations[i].docBlock.contentHash = keccak256(abi.encode(contentSeed, i));
            signatures[i] = _sign(ATTESTER_PRIVATE_KEY, attestations[i]);
            parentHash = chain.hashDocBlock(attestations[i].docBlock);
        }

        (uint256 storedCount, uint256 skippedCount) = chain.attestBatch(attestations, signatures);

        assertEq(storedCount, dayCount);
        assertEq(skippedCount, 0);
        for (uint256 i = 0; i < dayCount; i++) {
            bytes32 key = chain.attestationKey(
                attestations[i].attester,
                attestations[i].onBehalfOf,
                attestations[i].docBlock,
                keccak256(bytes(attestations[i].uri))
            );
            assertTrue(chain.attested(key));
        }
    }

    /// @dev Build a parent-linked run of daily attestations, mirroring how an RSO
    /// node attests consecutive archive days.
    function _chainedBatch(uint256 privateKey, uint64 firstDocRef, uint256 dayCount)
        private
        returns (DocChain.DocAttestation[] memory attestations, bytes[] memory signatures)
    {
        attestations = new DocChain.DocAttestation[](dayCount);
        signatures = new bytes[](dayCount);
        address signer = vm.addr(privateKey);
        bytes32 parentHash = bytes32(0);

        for (uint256 i = 0; i < dayCount; i++) {
            attestations[i] = _attestation(signer);
            attestations[i].docBlock.docRef = uint64(firstDocRef + i * 1_000_000);
            attestations[i].docBlock.parentHash = parentHash;
            attestations[i].docBlock.contentHash = keccak256(abi.encode("day", i));
            signatures[i] = _sign(privateKey, attestations[i]);
            parentHash = chain.hashDocBlock(attestations[i].docBlock);
        }
    }

    function _attestation(address signer) private view returns (DocChain.DocAttestation memory) {
        return _attestationFor(signer, address(0));
    }

    function _attestationFor(address signer, address onBehalfOf)
        private
        view
        returns (DocChain.DocAttestation memory)
    {
        return DocChain.DocAttestation({
            attester: signer,
            onBehalfOf: onBehalfOf,
            docBlock: DocChain.DocBlock({
                docChainId: DOC_CHAIN_ID,
                docRef: 20260506000000,
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

    function assertEq(uint256 actual, uint256 expected) private pure {
        if (actual != expected) {
            revert("assert uint256 eq failed");
        }
    }

    function assertNotEq(bytes32 actual, bytes32 expected) private pure {
        if (actual == expected) {
            revert("assert bytes32 not eq failed");
        }
    }
}
