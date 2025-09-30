"""
Configuration for TACo Smart Wallet operations
"""

import os
from dataclasses import dataclass
from typing import Optional
from web3 import Web3

# Network constants
ENTRYPOINT_V07 = "0x0000000071727De22E5E9d8BAf0edAc6f37da032"

# Smart Account Factory - Standard Infinitism SimpleAccountFactory
SMART_ACCOUNT_FACTORY = "0x9406Cc6185a346906296840746125a0E44976454"

# Default gas limits for UserOperations
DEFAULT_GAS_LIMITS = {
    "call": 300000,
    "verification": 1000000,
    "pre_verification": 60000,
    "fee": 1100000
}


def get_smart_account_address(user_id: str) -> str:
    """
    Compute the deterministic ERC-4337 smart account address for a user

    Uses the user's Discord ID as salt for CREATE2 deployment through SimpleAccountFactory
    No private keys needed - TACo handles all signing
    """
    # Convert user_id to salt for CREATE2
    salt = int(user_id).to_bytes(32, byteorder='big')

    # For SimpleAccountFactory, we need the initCodeHash
    # This should be the actual keccak256 hash of the SimpleAccount creation bytecode
    # For now, using a deterministic placeholder until we get the real value
    initcode_placeholder = Web3.keccak(f"SimpleAccount_initcode_{ENTRYPOINT_V07}".encode())

    # Proper CREATE2: keccak256(0xff + factory + salt + initcode_hash)[12:]
    factory_bytes = Web3.to_bytes(hexstr=SMART_ACCOUNT_FACTORY)
    create2_input = b'\xff' + factory_bytes + salt + initcode_placeholder
    address_hash = Web3.keccak(create2_input)

    # Take last 20 bytes as address
    address = '0x' + address_hash.hex()[-40:]
    return Web3.to_checksum_address(address)


@dataclass
class SmartAccountConfig:
    """Configuration for TACo Smart Wallet operations"""

    def __init__(self, user_id: Optional[str] = None):
        # Network configuration
        self.rpc_url = "https://sepolia.base.org"
        self.chain_id = 84532
        self.entry_point_address = ENTRYPOINT_V07

        # Smart account configuration
        self.factory_address = SMART_ACCOUNT_FACTORY

        # Generate user-specific smart account address if user_id provided
        if user_id:
            self.smart_account_address = get_smart_account_address(user_id)
            self.user_id = user_id
        else:
            # Fallback for backwards compatibility
            self.smart_account_address = "0xBF151420A84A6Bb7b1213d8269a5F1fe43FC3276"
            self.user_id = None

        # TACo network configuration (via Porter gateway)
        self.porter_url = "https://porter-lynx.nucypher.io"
        self.cohort_id = 2

        # Bundler configuration
        pimlico_api_key = os.environ.get('PIMLICO_API_KEY')
        if not pimlico_api_key:
            raise ValueError("PIMLICO_API_KEY environment variable is required")
        self.bundler_url = f"https://api.pimlico.io/v2/base-sepolia/rpc?apikey={pimlico_api_key}"
