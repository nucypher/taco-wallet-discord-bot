"""
Main TACo Smart Wallet service orchestration
"""

import logging
from typing import Dict
from web3 import Web3

from config import SmartAccountConfig
from bundler import BundlerClient
from porter import PorterSignatureService
from user_operations import create_eth_transfer_user_operation

logger = logging.getLogger(__name__)


class TacoSmartWalletService:
    """Main service for TACo-powered smart wallet operations"""
    
    def __init__(self, config: SmartAccountConfig):
        self.config = config
        self.web3 = Web3(Web3.HTTPProvider(config.rpc_url))
        self.bundler_client = BundlerClient(config)
        self.porter_service = PorterSignatureService(config)
        
        logger.info(f"TACo smart wallet service initialized for {config.smart_account_address}")

    async def send_eth(self, user_id: str, recipient: str, amount_eth: float) -> Dict:
        """Send ETH from smart account to recipient"""
        amount_wei = int(amount_eth * 10**18)
        
        # Validate balance
        self._validate_balance(amount_wei, amount_eth)
        
        # Create and optimize UserOperation
        user_operation = create_eth_transfer_user_operation(
            smart_account=self.config.smart_account_address,
            to_address=recipient,
            amount_wei=amount_wei,
            nonce=self._get_nonce()
        )
        
        user_operation = self._optimize_gas_settings(user_operation)
        
        # Sign and submit
        signed_user_operation = await self.porter_service.sign_user_operation(
            user_operation, f"Send {amount_eth} ETH to {recipient}"
        )
        
        bundler_result = self.bundler_client.send_user_operation(signed_user_operation)
        
        # Return result
        return self._format_transfer_result(bundler_result, recipient, amount_eth)



    def _validate_balance(self, amount_wei: int, amount_eth: float) -> None:
        """Validate sufficient balance for transfer"""
        smart_account_checksum = self.web3.to_checksum_address(self.config.smart_account_address)
        balance_wei = self.web3.eth.get_balance(smart_account_checksum)
        balance_eth = self.web3.from_wei(balance_wei, 'ether')
        
        logger.info(f"Sending {amount_eth} ETH (balance: {balance_eth} ETH)")
        
        if balance_wei < amount_wei:
            raise Exception(f"Insufficient balance: {balance_eth} ETH < {amount_eth} ETH")

    def _optimize_gas_settings(self, user_operation):
        """Update UserOperation with optimized gas settings from Pimlico"""
        
        # Update gas prices
        gas_prices = self.bundler_client.get_user_operation_gas_price()
        if gas_prices and 'fast' in gas_prices:
            fast_prices = gas_prices['fast']
            if 'maxFeePerGas' in fast_prices:
                user_operation.max_fee_per_gas = int(fast_prices['maxFeePerGas'], 16)
            if 'maxPriorityFeePerGas' in fast_prices:
                user_operation.max_priority_fee_per_gas = int(fast_prices['maxPriorityFeePerGas'], 16)
        
        # Update gas limits with estimates
        gas_estimates = self.bundler_client.estimate_user_operation_gas(user_operation)
        if gas_estimates:
            if 'callGasLimit' in gas_estimates:
                user_operation.call_gas_limit = int(gas_estimates['callGasLimit'], 16)
            if 'verificationGasLimit' in gas_estimates:
                # Add 50% buffer for TACo threshold signature verification
                base_gas = int(gas_estimates['verificationGasLimit'], 16)
                user_operation.verification_gas_limit = int(base_gas * 1.5)
            if 'preVerificationGas' in gas_estimates:
                user_operation.pre_verification_gas = int(gas_estimates['preVerificationGas'], 16)
        
        return user_operation

    def _format_transfer_result(self, bundler_result: Dict, recipient: str, amount_eth: float) -> Dict:
        """Format the transfer result for consistent response"""
        base_result = {
            'smart_account': self.config.smart_account_address,
            'recipient': recipient,
            'amount_eth': amount_eth,
        }
        
        if bundler_result['success']:
            logger.info("ETH transfer submitted successfully")
            return {
                **base_result,
                'user_operation_hash': bundler_result['user_operation_hash'],
                'status': 'submitted',
                'success': True
            }
        else:
            logger.error(f"Failed to submit ETH transfer: {bundler_result['error']}")
            return {
                **base_result,
                'error': bundler_result['error'],
                'status': 'failed',
                'success': False
            }

    def _get_nonce(self) -> int:
        """Get current nonce for smart account from EntryPoint"""
        get_nonce_abi = [{
            "inputs": [{"name": "sender", "type": "address"}, {"name": "key", "type": "uint192"}],
            "name": "getNonce",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        }]
        
        entry_point_contract = self.web3.eth.contract(
            address=self.web3.to_checksum_address(self.config.entry_point_address),
            abi=get_nonce_abi
        )
        
        nonce = entry_point_contract.functions.getNonce(
            self.web3.to_checksum_address(self.config.smart_account_address),
            0  # Default key
        ).call()
        
        logger.info(f"Current nonce: {nonce}")
        return nonce


def create_taco_smart_wallet_service() -> TacoSmartWalletService:
    """Create a TACo Smart Wallet service with default configuration"""
    return TacoSmartWalletService(SmartAccountConfig()) 