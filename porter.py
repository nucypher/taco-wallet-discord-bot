"""
TACo threshold signature service via Porter gateway for NuCypher UserOperations
"""

import logging
import base64
import threading
from typing import List, Dict
import requests

from nucypher.network.signing import (
    SignatureResponse, 
    UserOperationSignatureRequest, 
    AAVersion, 
    UserOperation
)

from config import SmartAccountConfig

logger = logging.getLogger(__name__)


class PorterSignatureService:
    """Handles signature requests to TACo network via Porter gateway for UserOperations using NuCypher threshold signatures"""
    
    def __init__(self, config: SmartAccountConfig, threshold: int = 2):
        self.config = config
        self.threshold = threshold

    async def sign_user_operation(self, user_operation: UserOperation, context: str) -> UserOperation:
        """Sign a UserOperation using TACo threshold signatures via Porter gateway"""
        logger.info(f"Signing UserOperation with TACo via Porter: {context}")
        
        # Get Discord context for Porter
        discord_context = self._get_discord_context()
        porter_context = {
            ":message": discord_context['message_hex'],
            ":signature": discord_context['signature']
        }
        
        # Create signing request
        signing_request = UserOperationSignatureRequest(
            user_op=user_operation,
            cohort_id=self.config.cohort_id,
            chain_id=self.config.chain_id,
            aa_version=AAVersion.MDT,
            context=porter_context
        )
        
        # Get signatures from Porter
        signatures = await self._request_signatures(signing_request)
        
        # Return UserOperation with combined signature
        return self._create_signed_user_operation(user_operation, signatures)
    
    def _get_discord_context(self) -> Dict:
        """Get Discord context from current thread"""
        discord_context = getattr(threading.current_thread(), 'discord_context', None)
        if not discord_context:
            raise Exception("Discord context required for Porter signatures")
        return discord_context
    
    async def _request_signatures(self, signing_request: UserOperationSignatureRequest) -> List[str]:
        """Request threshold signatures from TACo network via Porter gateway"""
        # Prepare request
        signing_request_b64 = base64.b64encode(bytes(signing_request)).decode()
        ursulas = self._get_ursulas()
        
        request_data = {
            'signing_requests': {ursula: signing_request_b64 for ursula in ursulas},
            'threshold': self.threshold
        }
        
        # Send to Porter
        response = requests.post(
            f"{self.config.porter_url}/sign",
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        response.raise_for_status()
        
        # Process response
        result = response.json()
        signing_results = result.get('result', {}).get('signing_results', {})
        
        if signing_results.get('errors'):
            raise Exception(f"TACo signing failed: {signing_results['errors']}")
        
        signatures = signing_results.get('signatures', {})
        if not signatures:
            raise Exception("No signatures in TACo response")
        
        # Extract signature responses
        signature_responses = []
        for ursula_address, sig_data in signatures.items():
            if isinstance(sig_data, list) and len(sig_data) >= 2:
                response_data = base64.b64decode(sig_data[1])
                sig_response = SignatureResponse.from_bytes(response_data=response_data)
                signature_responses.append(sig_response)
        
        if not signature_responses:
            raise Exception("No valid signature responses from TACo network")
        
        logger.info(f"Got {len(signature_responses)} TACo threshold signatures")
        return [resp.signature.hex() for resp in signature_responses]
    
    def _create_signed_user_operation(self, user_operation: UserOperation, signatures: List[str]) -> UserOperation:
        """Create new UserOperation with combined signatures"""
        combined_signature = '0x' + ''.join(sig.replace('0x', '') for sig in signatures)
        signature_bytes = bytes.fromhex(combined_signature[2:])
        
        # Create new UserOperation with signature (immutable pattern)
        return UserOperation(
            sender=user_operation.sender,
            nonce=user_operation.nonce,
            factory=user_operation.factory,
            factory_data=user_operation.factory_data,
            call_data=user_operation.call_data,
            call_gas_limit=user_operation.call_gas_limit,
            verification_gas_limit=user_operation.verification_gas_limit,
            pre_verification_gas=user_operation.pre_verification_gas,
            max_fee_per_gas=user_operation.max_fee_per_gas,
            max_priority_fee_per_gas=user_operation.max_priority_fee_per_gas,
            paymaster=user_operation.paymaster,
            paymaster_verification_gas_limit=user_operation.paymaster_verification_gas_limit,
            paymaster_post_op_gas_limit=user_operation.paymaster_post_op_gas_limit,
            paymaster_data=user_operation.paymaster_data,
            signature=signature_bytes
        )

    def _get_ursulas(self, quantity: int = 3) -> List[str]:
        """Get TACo node checksums from network via Porter gateway"""
        response = requests.get(
            f"{self.config.porter_url}/get_ursulas",
            params={"quantity": quantity},
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        ursulas = data["result"]["ursulas"]
        return [ursula["checksum_address"] for ursula in ursulas] 