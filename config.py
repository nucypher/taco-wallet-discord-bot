"""
Configuration for TACo Smart Wallet operations
"""

import os
from dataclasses import dataclass

# Network constants
ENTRYPOINT_V07 = "0x0000000071727De22E5E9d8BAf0edAc6f37da032"

# Default gas limits for UserOperations
DEFAULT_GAS_LIMITS = {
    "call": 300000,
    "verification": 1000000, 
    "pre_verification": 60000,
    "fee": 1100000
}


@dataclass
class SmartAccountConfig:
    """Configuration for TACo Smart Wallet operations"""
    
    def __init__(self):
        # Network configuration
        self.rpc_url = "https://sepolia.base.org"
        self.chain_id = 84532
        self.entry_point_address = ENTRYPOINT_V07
        self.smart_account_address = "0x2a456304C6d79C91Ef8a02Bd87f85486d5d2d7E0"
        
        # TACo network configuration (via Porter gateway)
        self.porter_url = "https://porter-lynx.nucypher.io"
        self.cohort_id = int(os.environ.get('COHORT_ID'))
        self.eth_endpoint = os.environ.get('DEMO_L1_PROVIDER_URI', 'https://sepolia.drpc.org')
        
        # Bundler configuration
        pimlico_api_key = os.environ.get('PIMLICO_API_KEY')
        if not pimlico_api_key:
            raise ValueError("PIMLICO_API_KEY environment variable is required")
        self.bundler_url = f"https://api.pimlico.io/v2/base-sepolia/rpc?apikey={pimlico_api_key}" 