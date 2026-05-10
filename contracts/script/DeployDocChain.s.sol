// SPDX-License-Identifier: CC0-1.0
pragma solidity 0.8.35;

import { DocChain } from "../src/DocChain.sol";

interface Vm {
    function envUint(string calldata name) external returns (uint256);
    function startBroadcast(uint256 privateKey) external;
    function stopBroadcast() external;
}

contract DeployDocChain {
    Vm private constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    function run() external returns (DocChain deployed) {
        uint256 privateKey = vm.envUint("PRIVATE_KEY");

        vm.startBroadcast(privateKey);
        deployed = new DocChain();
        vm.stopBroadcast();
    }
}
