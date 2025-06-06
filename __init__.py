"""
TACo Smart Wallet Reference Implementation

A clean, modular implementation demonstrating TACo threshold signatures
with ERC-4337 smart wallets via Porter gateway and Pimlico bundler integration.
Smart wallet provider agnostic.
"""

# Main service
from smart_account import TacoSmartWalletService, create_taco_smart_wallet_service

# Configuration
from config import SmartAccountConfig

# Individual components for advanced usage
from bundler import BundlerClient, convert_user_operation_to_pimlico_format
from porter import PorterSignatureService
from user_operations import create_eth_transfer_user_operation

__version__ = "1.0.0"

__all__ = [
    "TacoSmartWalletService",
    "create_taco_smart_wallet_service",
    "SmartAccountConfig",
    "BundlerClient",
    "PorterSignatureService",
    "create_eth_transfer_user_operation",
    "convert_user_operation_to_pimlico_format",
] 