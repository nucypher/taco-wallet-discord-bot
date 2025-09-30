"""
UserOperation creation utilities for TACo Smart Wallets
"""

import logging
from web3 import Web3
from eth_abi import encode
from nucypher.network.signing import UserOperation

from config import DEFAULT_GAS_LIMITS

logger = logging.getLogger(__name__)

# Function selector for execute((address,uint256,bytes))
EXECUTE_SELECTOR = Web3.keccak(text="execute((address,uint256,bytes))")[:4]


def create_eth_transfer_user_operation(
    smart_account: str,
    to_address: str,
    amount_wei: int,
    nonce: int,
    web3: Web3,
    user_id: str = None
) -> UserOperation:
    """Create ETH transfer UserOperation using tuple-based execute function"""

    # Check if smart account exists
    code = web3.eth.get_code(smart_account)
    account_exists = len(code) > 0

    # Set factory and factory_data for account deployment
    factory = None
    factory_data = b''

    if not account_exists and user_id:
        from config import SMART_ACCOUNT_FACTORY, ENTRYPOINT_V07

        # Account needs to be deployed - set initCode
        factory = SMART_ACCOUNT_FACTORY

        # createAccount(owner, salt) function selector
        CREATE_ACCOUNT_SELECTOR = Web3.keccak(text="createAccount(address,uint256)")[:4]

        # For demo, use a dummy owner address (in production, TACo would provide this)
        dummy_owner = "0x" + "0" * 40  # TACo will be the actual signer
        salt = int(user_id)

        factory_data = CREATE_ACCOUNT_SELECTOR + encode(
            ['address', 'uint256'],
            [dummy_owner, salt]
        )

        logger.info(f"Account {smart_account} will be deployed with salt {salt}")

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
        factory=factory,
        factory_data=factory_data,
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
        signature=b''
    )
