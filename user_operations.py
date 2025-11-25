"""
UserOperation creation utilities for TACo Smart Wallets
"""

import logging
from dataclasses import dataclass
from web3 import Web3
from eth_abi import encode
from nucypher_core import UserOperation

from config import DEFAULT_GAS_LIMITS

logger = logging.getLogger(__name__)


@dataclass
class SignedUserOperation:
    """Wrapper holding a UserOperation and its signature"""
    user_operation: UserOperation
    signature: bytes

# Function selector for execute((address,uint256,bytes))
EXECUTE_SELECTOR = Web3.keccak(text="execute((address,uint256,bytes))")[:4]


def create_eth_transfer_user_operation(
    smart_account: str, 
    to_address: str, 
    amount_wei: int, 
    nonce: int
) -> UserOperation:
    """Create ETH transfer UserOperation using tuple-based execute function"""
    
    # Encode execute((address,uint256,bytes)) call
    encoded_params = encode(
        ['(address,uint256,bytes)'], 
        [(Web3.to_checksum_address(to_address), amount_wei, b'')]
    )
    calldata = EXECUTE_SELECTOR + encoded_params
    
    logger.info(f"Created ETH transfer: {amount_wei} wei to {to_address}")
    
    return UserOperation(
        sender=smart_account,
        nonce=nonce,
        factory=None,
        factory_data=b'',
        call_data=calldata,
        call_gas_limit=DEFAULT_GAS_LIMITS["call"],
        verification_gas_limit=DEFAULT_GAS_LIMITS["verification"],
        pre_verification_gas=DEFAULT_GAS_LIMITS["pre_verification"],
        max_fee_per_gas=DEFAULT_GAS_LIMITS["fee"],
        max_priority_fee_per_gas=DEFAULT_GAS_LIMITS["fee"],
        paymaster=None,
        paymaster_verification_gas_limit=0,
        paymaster_post_op_gas_limit=0,
        paymaster_data=b'',
    ) 