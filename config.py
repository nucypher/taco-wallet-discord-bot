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
# This is the canonical ERC-4337 SimpleAccountFactory deployed on most networks
SMART_ACCOUNT_FACTORY = "0x9406Cc6185a346906296840746125a0E44976454"  # Infinitism SimpleAccountFactory

# Default gas limits for UserOperations
DEFAULT_GAS_LIMITS = {
    "call": 300000,
    "verification": 1000000,
    "pre_verification": 60000,
    "fee": 1100000
}


def compute_smart_account_address(user_id: str, factory_address: str = SMART_ACCOUNT_FACTORY) -> str:
    """
    Compute deterministic smart account address using user ID as salt

    This uses CREATE2 deterministic address generation:
    address = keccak256(0xff + factory_address + salt + keccak256(initcode))[12:]

    For SimpleAccountFactory, the salt is the user_id converted to uint256
    """
    # Convert user_id to a 32-byte salt (pad with zeros)
    user_id_int = int(user_id)
    salt = user_id_int.to_bytes(32, byteorder='big')

    # For now, return a deterministic address based on user_id
    # In production, this should use the actual factory contract and CREATE2
    salt_hash = Web3.keccak(salt)

    # Simplified deterministic address generation
    # Replace this with actual CREATE2 calculation using your factory
    factory_bytes = Web3.to_bytes(hexstr=factory_address)
    combined = factory_bytes + salt + salt_hash
    address_hash = Web3.keccak(combined)

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
            self.smart_account_address = compute_smart_account_address(user_id)
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
