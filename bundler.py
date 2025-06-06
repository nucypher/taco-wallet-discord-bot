"""
Pimlico bundler integration and format conversion utilities for TACo smart wallets
"""

import logging
from typing import List, Dict, Optional
import requests
from nucypher.network.signing import UserOperation

from config import SmartAccountConfig

logger = logging.getLogger(__name__)

# Field mappings for NuCypher -> Pimlico conversion
FIELD_MAPPINGS = {
    "sender": "sender",
    "nonce": ("nonce", hex),
    "call_data": "callData", 
    "call_gas_limit": ("callGasLimit", hex),
    "verification_gas_limit": ("verificationGasLimit", hex),
    "pre_verification_gas": ("preVerificationGas", hex),
    "max_fee_per_gas": ("maxFeePerGas", hex),
    "max_priority_fee_per_gas": ("maxPriorityFeePerGas", hex),
    "signature": "signature"
}


def convert_user_operation_to_pimlico_format(user_operation: UserOperation) -> Dict:
    """Convert NuCypher UserOperation to Pimlico bundler format (EntryPoint v0.7)"""
    nucypher_dict = user_operation.to_dict()
    pimlico_dict = {}
    
    # Map basic fields
    for nucypher_field, pimlico_mapping in FIELD_MAPPINGS.items():
        value = nucypher_dict[nucypher_field]
        if isinstance(pimlico_mapping, tuple):
            pimlico_field, converter = pimlico_mapping
            pimlico_dict[pimlico_field] = converter(value)
        else:
            pimlico_dict[pimlico_mapping] = value
    
    # Handle optional factory fields
    factory = nucypher_dict["factory"]
    pimlico_dict.update({
        "factory": factory,
        "factoryData": nucypher_dict["factory_data"] if factory else None
    })
    
    # Handle optional paymaster fields  
    paymaster = nucypher_dict["paymaster"]
    if paymaster:
        pimlico_dict.update({
            "paymaster": paymaster,
            "paymasterVerificationGasLimit": hex(nucypher_dict["paymaster_verification_gas_limit"]),
            "paymasterPostOpGasLimit": hex(nucypher_dict["paymaster_post_op_gas_limit"]),
            "paymasterData": nucypher_dict["paymaster_data"]
        })
    else:
        pimlico_dict.update({
            "paymaster": None,
            "paymasterVerificationGasLimit": None, 
            "paymasterPostOpGasLimit": None,
            "paymasterData": None
        })
    
    return pimlico_dict


class BundlerClient:
    """Client for interacting with ERC-4337 bundlers (Pimlico)"""
    
    def __init__(self, config: SmartAccountConfig):
        self.config = config
    
    def estimate_user_operation_gas(self, user_operation: UserOperation) -> Optional[Dict]:
        """Estimate gas for UserOperation using Pimlico API"""
        user_op_dict = convert_user_operation_to_pimlico_format(user_operation)
        user_op_dict['signature'] = "0x" + "0" * 130  # Dummy signature
        
        return self._make_bundler_request("eth_estimateUserOperationGas", [user_op_dict, self.config.entry_point_address])
    
    def get_user_operation_gas_price(self) -> Optional[Dict]:
        """Get current gas prices from Pimlico"""
        return self._make_bundler_request("pimlico_getUserOperationGasPrice", [])
    
    def send_user_operation(self, user_operation: UserOperation) -> Dict:
        """Send UserOperation to bundler and return result"""
        logger.info("Sending UserOperation to bundler...")
        
        user_op_dict = convert_user_operation_to_pimlico_format(user_operation)
        result = self._make_bundler_request("eth_sendUserOperation", [user_op_dict, self.config.entry_point_address])
        
        if result:
            logger.info(f"UserOperation sent successfully: {result}")
            return {
                'success': True,
                'user_operation_hash': result,
                'status': 'submitted'
            }
        else:
            return {
                'success': False,
                'error': 'Failed to send UserOperation',
                'status': 'failed'
            }
    
    def _make_bundler_request(self, method: str, params: List) -> Optional[Dict]:
        """Make JSON-RPC request to bundler"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        
        try:
            response = requests.post(
                self.config.bundler_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'result' in result:
                    return result['result']
                elif 'error' in result:
                    error = result['error']
                    logger.error(f"Bundler error: {error.get('message', 'Unknown error')}")
                    return None
            else:
                logger.error(f"HTTP error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None 