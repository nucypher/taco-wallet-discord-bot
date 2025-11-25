"""
TACo threshold signature service via Porter gateway for NuCypher UserOperations
"""

import logging
import base64
import threading
from typing import List, Dict
import requests

import json

from nucypher_core import (
    AAVersion,
    Context,
    EncryptedThresholdSignatureResponse,
    SessionStaticKey,
    SessionStaticSecret,
    SignatureResponse,
    UserOperation,
    UserOperationSignatureRequest,
)
from nucypher.blockchain.eth import domains
from nucypher.blockchain.eth.agents import SigningCoordinatorAgent
from nucypher.blockchain.eth.registry import ContractRegistry

from config import SmartAccountConfig
from user_operations import SignedUserOperation
from hexbytes import HexBytes

logger = logging.getLogger(__name__)


class PorterSignatureService:
    """Handles signature requests to TACo network via Porter gateway for UserOperations using NuCypher threshold signatures"""

    def __init__(self, config: SmartAccountConfig, threshold: int = 2):
        self.config = config
        self.threshold = threshold

        # Set up SigningCoordinatorAgent for fetching cohort info with signing keys
        registry = ContractRegistry.from_latest_publication(domain=domains.LYNX)
        self.signing_coordinator_agent = SigningCoordinatorAgent(
            blockchain_endpoint=config.eth_endpoint,
            registry=registry,
        )

    async def sign_user_operation(self, user_operation: UserOperation, context: str) -> SignedUserOperation:
        """Sign a UserOperation using TACo threshold signatures via Porter gateway"""
        logger.info(f"Signing UserOperation with TACo via Porter: {context}")

        # Get Discord context for Porter
        discord_context = self._get_discord_context()
        message_hex = HexBytes(discord_context['message_hex']).hex()
        porter_context = Context(json.dumps({
            ":message": message_hex,
            ":signature": discord_context['signature'],
            ":discordPayload": discord_context["body"]
        }))

        # Create signing request
        signing_request = UserOperationSignatureRequest(
            user_op=user_operation,
            cohort_id=self.config.cohort_id,
            chain_id=self.config.chain_id,
            aa_version=AAVersion.MDT,
            context=porter_context
        )
        logger.info(f"UserOp details: sender={user_operation.sender}, nonce={user_operation.nonce}, chain_id={self.config.chain_id}")
        logger.info(f"UserOp call_data: {user_operation.call_data.hex()[:40]}...")

        # Get signatures from Porter
        signatures = await self._request_signatures(signing_request)

        # Return SignedUserOperation with combined signature
        return self._create_signed_user_operation(user_operation, signatures)
    
    def _get_discord_context(self) -> Dict:
        """Get Discord context from current thread"""
        discord_context = getattr(threading.current_thread(), 'discord_context', None)
        if not discord_context:
            raise Exception("Discord context required for Porter signatures")
        return discord_context
    
    async def _request_signatures(self, signing_request: UserOperationSignatureRequest) -> List[SignatureResponse]:
        """Request threshold signatures from TACo network via Porter gateway using encrypted requests"""
        # Generate ephemeral keypair for e2e encryption
        requester_sk = SessionStaticSecret.random()
        requester_pk = requester_sk.public_key()

        # Get cohort signers info with their public keys
        signers_info = self._get_signers_info()

        # Build encrypted signing requests and shared secrets for each signer
        encrypted_signing_requests = {}
        shared_secrets = {}

        for ursula_address, signer_public_key in signers_info.items():
            # Derive shared secret for this signer
            shared_secret = requester_sk.derive_shared_secret(signer_public_key)
            shared_secrets[ursula_address] = shared_secret

            # Encrypt the signing request
            encrypted_request = signing_request.encrypt(
                shared_secret=shared_secret,
                requester_public_key=requester_pk
            )
            encrypted_signing_requests[ursula_address] = base64.b64encode(
                bytes(encrypted_request)
            ).decode()

        # Send encrypted requests to Porter
        request_data = {
            'encrypted_signing_requests': encrypted_signing_requests,
            'threshold': self.threshold
        }

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

        encrypted_signature_responses = signing_results.get('encrypted_signature_responses', {})
        if not encrypted_signature_responses:
            raise Exception("No encrypted signature responses in TACo response")

        # Decrypt signature responses using corresponding shared secrets
        signature_responses = []
        for ursula_address, encrypted_sig_data in encrypted_signature_responses.items():
            if ursula_address not in shared_secrets:
                logger.warning(f"No shared secret for {ursula_address}, skipping")
                continue

            # Decode and decrypt the response
            encrypted_response = EncryptedThresholdSignatureResponse.from_bytes(
                base64.b64decode(encrypted_sig_data)
            )
            sig_response = encrypted_response.decrypt(
                shared_secret=shared_secrets[ursula_address]
            )
            logger.info(f"Provider {ursula_address} -> Signer {sig_response.signer}")
            signature_responses.append(sig_response)

        # sort signature responses by signer
        signature_responses = sorted(signature_responses, key=lambda r: int(r.signer, 16))

        if not signature_responses:
            raise Exception("No valid signature responses from TACo network")

        # Note: Not sorting - matching old behavior that was working
        logger.info(f"Got {len(signature_responses)} TACo threshold signatures")
        for r in signature_responses:
            sig_hex = bytes(r.signature).hex()
            logger.info(f"Signer: {r.signer}, sig_type: {r.signature_type}")
            logger.info(f"  Full hash signed: {r.hash.hex()}")
            logger.info(f"  Full signature: {sig_hex}")
        return signature_responses

    def _create_signed_user_operation(self, user_operation: UserOperation, signature_responses: List[SignatureResponse]) -> SignedUserOperation:
        """Create SignedUserOperation with combined signatures"""
        # Concatenate raw signature bytes (already sorted by signer)
        # Note: r.signature is already bytes, no need to convert
        combined_signature = b"".join([r.signature for r in signature_responses])
        logger.info(f"Combined signature length: {len(combined_signature)}, hex: {combined_signature.hex()[:60]}...")

        return SignedUserOperation(
            user_operation=user_operation,
            signature=combined_signature
        )

    def _get_signers_info(self) -> Dict[str, SessionStaticKey]:
        """Get cohort signers with their public keys for encrypted requests"""
        signing_cohort = self.signing_coordinator_agent.get_signing_cohort(
            self.config.cohort_id
        )
        logger.info(f"Cohort {self.config.cohort_id} has {len(signing_cohort.signers)} signers")
        for signer in signing_cohort.signers:
            logger.info(f"Cohort signer: provider={signer.provider}")
        return {
            signer.provider: SessionStaticKey.from_bytes(signer.signing_request_key)
            for signer in signing_cohort.signers
        } 