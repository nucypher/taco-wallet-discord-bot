"""
Pimlico bundler integration and format conversion utilities for TACo smart wallets
"""

import logging
from typing import List, Dict, Optional, Union
import requests
from nucypher_core import UserOperation

from config import SmartAccountConfig
from user_operations import SignedUserOperation

logger = logging.getLogger(__name__)


def convert_user_operation_to_pimlico_format(
    user_op: Union[UserOperation, SignedUserOperation],
    signature: bytes = None
) -> Dict:
    """Convert NuCypher UserOperation to Pimlico bundler format (EntryPoint v0.7)"""
    # Handle SignedUserOperation wrapper
    if isinstance(user_op, SignedUserOperation):
        op = user_op.user_operation
        signature = user_op.signature
    else:
        op = user_op

    # Build pimlico dict from direct attribute access
    pimlico_dict = {
        "sender": op.sender,
        "nonce": hex(op.nonce),
        "callData": "0x" + op.call_data.hex() if isinstance(op.call_data, bytes) else op.call_data,
        "callGasLimit": hex(op.call_gas_limit),
        "verificationGasLimit": hex(op.verification_gas_limit),
        "preVerificationGas": hex(op.pre_verification_gas),
        "maxFeePerGas": hex(op.max_fee_per_gas),
        "maxPriorityFeePerGas": hex(op.max_priority_fee_per_gas),
    }

    # Add signature
    if signature:
        pimlico_dict["signature"] = "0x" + signature.hex() if isinstance(signature, bytes) else signature
    else:
        pimlico_dict["signature"] = "0x"

    # Handle optional factory fields
    factory = op.factory
    pimlico_dict.update({
        "factory": factory,
        "factoryData": "0x" + op.factory_data.hex() if factory and op.factory_data else None
    })

    # Handle optional paymaster fields
    paymaster = op.paymaster
    if paymaster:
        pimlico_dict.update({
            "paymaster": paymaster,
            "paymasterVerificationGasLimit": hex(op.paymaster_verification_gas_limit),
            "paymasterPostOpGasLimit": hex(op.paymaster_post_op_gas_limit),
            "paymasterData": "0x" + op.paymaster_data.hex() if op.paymaster_data else "0x"
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
    
    def send_user_operation(self, signed_user_op: SignedUserOperation) -> Dict:
        """Send SignedUserOperation to bundler and return result"""
        logger.info("Sending UserOperation to bundler...")

        user_op_dict = convert_user_operation_to_pimlico_format(signed_user_op)
        logger.info(f"Full UserOp to bundler: {user_op_dict}")
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