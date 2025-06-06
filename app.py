
"""
TACo Smart Wallet Discord Bot

A clean Discord bot implementation that demonstrates:
1. Discord slash command handling with signature verification
2. ETH transfers using TACo threshold signatures via Porter gateway
3. Integration with NuCypher UserOperations and Pimlico bundler
"""

import logging
import os
import threading
import re
import asyncio
from typing import Dict, Any, Optional

import requests
from flask import Flask, request, jsonify, abort
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from smart_account import TacoSmartWalletService
from config import SmartAccountConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DISCORD_WEBHOOK_BASE_URL = "https://discord.com/api/v10/webhooks"
DISCORD_SIGNATURE_HEADER = "X-Signature-Ed25519"
DISCORD_TIMESTAMP_HEADER = "X-Signature-Timestamp"

# Discord interaction types
DISCORD_PING_TYPE = 1
DISCORD_COMMAND_TYPE = 2
DISCORD_DEFERRED_RESPONSE_TYPE = 5

# Server defaults
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080





def get_discord_public_key() -> str:
    """Get Discord bot public key from environment variable"""
    key = os.environ.get('DISCORD_BOT_PUBLIC_KEY')
    if not key:
        raise ValueError("DISCORD_BOT_PUBLIC_KEY environment variable is required")
    return key


def send_discord_response(app_id: str, token: str, content: str) -> None:
    """Send a response back to Discord"""
    try:
        url = f"{DISCORD_WEBHOOK_BASE_URL}/{app_id}/{token}"
        response = requests.post(url, json={"content": content}, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to send Discord response: {e}")





def verify_discord_signature(signature: str, timestamp: str, body: str) -> None:
    """Verify Discord request signature"""
    try:
        verify_key = VerifyKey(key=bytes.fromhex(get_discord_public_key()))
        signed_message = f"{timestamp}{body}".encode("utf-8")
        verify_key.verify(smessage=signed_message, signature=bytes.fromhex(signature))
    except BadSignatureError:
        logger.warning("Invalid Discord signature")
        abort(code=401, description="Invalid request signature")
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        abort(code=500, description="Internal server error")


def extract_user_id(payload: Dict[str, Any]) -> str:
    """Extract Discord user ID from interaction payload"""
    # Try guild interactions first
    if "member" in payload and "user" in payload["member"]:
        return payload["member"]["user"]["id"]
    
    # Try DM interactions
    if "user" in payload:
        return payload["user"]["id"]
    
    raise Exception("Missing user ID in Discord interaction")


def parse_tip_request(amount: str, recipient: str) -> Dict[str, Any]:
    """Parse and validate tip request parameters"""
    # Validate amount
    try:
        amount_float = float(amount)
        if amount_float <= 0:
            return {"error": "❌ Amount must be greater than 0"}
        if amount_float > 100:  # Safety limit
            return {"error": "❌ Safety limit: Maximum tip amount is 100 ETH"}
    except ValueError:
        return {"error": "❌ Invalid amount format. Please use decimal format (e.g., 0.01)"}

    # Parse recipient
    if re.match(r"^<@!?(\d+)>$", recipient):
        # Discord user mention
        user_id = re.sub(r"^<@!?(\d+)>$", r"\1", recipient)
        recipient_address = f"0x{hash(user_id) % (16**40):040x}"
        recipient_display = f"<@{user_id}>"
    elif recipient.startswith("@"):
        # @username format
        username = recipient[1:]
        recipient_address = f"0x{hash(username) % (16**40):040x}"
        recipient_display = f"@{username}"
    elif re.match(r"^0x[a-fA-F0-9]{40}$", recipient):
        # Ethereum address
        recipient_address = recipient.lower()
        recipient_display = f"{recipient[:6]}...{recipient[-4:]}"
    else:
        return {"error": "❌ Invalid recipient. Use @username or Ethereum address (0x...)"}

    return {
        "amount": amount,
        "recipient_address": recipient_address,
        "recipient_display": recipient_display
    }


class DiscordInteractionHandler:
    """Handles Discord interactions and message processing"""

    def __init__(self):
        self.app = Flask(__name__)
        self.taco_service = TacoSmartWalletService(SmartAccountConfig())
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up Flask routes"""
        self.app.route("/interactions", methods=["POST"])(self.handle_interactions)
        self.app.route("/health", methods=["GET"])(self.health_check)

    def _handle_tip(
        self, user_id: str, amount: str, recipient: str, interaction_token: str, 
        application_id: str, body: str, timestamp: int, signature: str
    ) -> None:
        """Handle ETH tip operation for a specific user"""
        # Parse and validate request
        tip_data = parse_tip_request(amount, recipient)
        if "error" in tip_data:
            send_discord_response(application_id, interaction_token, tip_data["error"])
            return

        try:
            # Set Discord context for TACo signatures
            self._set_discord_context(timestamp, body, signature, user_id, amount, recipient)
            
            # Execute ETH transfer
            result = self._execute_eth_transfer(user_id, tip_data)
            
            # Format and send response
            content = self._format_tip_response(result, tip_data, user_id)
            
        except Exception as e:
            logger.error(f"TACo tip error for user {user_id}: {e}")
            content = self._format_error_response(e)

        send_discord_response(application_id, interaction_token, content)
    
    def _set_discord_context(self, timestamp: int, body: str, signature: str, 
                           user_id: str, amount: str, recipient: str) -> None:
        """Set Discord context for TACo signatures"""
        discord_context = {
            'message_hex': f"{timestamp}{body}".encode("utf-8").hex(),
            'signature': signature,
            'timestamp': timestamp,
            'command': 'tip',
            'user_id': user_id,
            'body': body,
            'amount': amount,
            'recipient': recipient
        }
        threading.current_thread().discord_context = discord_context
        logger.info(f"Set Discord context for TACo: tip {amount} ETH to {recipient}")
    
    def _execute_eth_transfer(self, user_id: str, tip_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ETH transfer using TACo threshold signatures"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.taco_service.send_eth(
                user_id=user_id,
                recipient=tip_data['recipient_address'],
                amount_eth=float(tip_data['amount'])
            )
        )
    
    def _format_tip_response(self, result: Dict[str, Any], tip_data: Dict[str, Any], user_id: str) -> str:
        """Format tip response message"""
        if result.get('success', False):
            return (
                f"✅ **ETH Transfer Submitted Successfully!**\n"
                f"Initiated by: `<@{user_id}>`\n"
                f"Amount: `{tip_data['amount']} ETH`\n"
                f"Recipient: `{tip_data['recipient_display']}`\n"
                f"Smart Account: `{result['smart_account'][:10]}...{result['smart_account'][-6:]}`\n"
                f"UserOp Hash: `{result['user_operation_hash'][:16]}...{result['user_operation_hash'][-6:]}`\n"
                f"Status: `{result['status']}`\n"
                f"Network: `Base Sepolia`"
            )
        else:
            return (
                f"❌ **ETH Transfer Failed**\n"
                f"Initiated by: `<@{user_id}>`\n"
                f"Amount: `{tip_data['amount']} ETH`\n"
                f"Recipient: `{tip_data['recipient_display']}`\n"
                f"Error: `{result.get('error', 'Unknown error')}`\n"
                f"Status: `{result['status']}`"
            )
    
    def _format_error_response(self, error: Exception) -> str:
        """Format error response message"""
        if 'decryption conditions not satisfied' in str(error).lower():
            return (
                f"❌ **TACo Signature Error**\n"
                f"TACo conditions not satisfied.\n"
                f"This means the Discord webhook context didn't meet\n"
                f"the access control requirements for real signatures."
            )
        else:
            return f"❌ Unexpected error processing TACo tip: {str(error)}"

    def handle_interactions(self):
        """Handle incoming Discord interactions"""
        try:
            payload = request.json
            signature = request.headers[DISCORD_SIGNATURE_HEADER]
            timestamp = request.headers[DISCORD_TIMESTAMP_HEADER]
            body = request.data.decode("utf-8")

            verify_discord_signature(signature, timestamp, body)

            # Handle PING
            if payload.get("type") == DISCORD_PING_TYPE:
                return jsonify({"type": DISCORD_PING_TYPE})

            # Handle slash commands
            if payload.get("type") == DISCORD_COMMAND_TYPE:
                return self._handle_slash_command(payload, signature, timestamp, body)

            return "", 204
        except Exception as e:
            logger.error(f"Interaction handling error: {e}")
            return jsonify({"error": "Internal server error"}), 500

    def _handle_slash_command(self, payload: Dict[str, Any], signature: str, timestamp: str, body: str):
        """Handle Discord slash commands"""
        data = payload.get("data", {})
        command_name = data.get("name")
        
        if command_name != "tip":
            return "", 204

        # Extract parameters
        user_id = extract_user_id(payload)
        options = data.get("options", [])
        amount = next((opt["value"] for opt in options if opt["name"] == "amount"), "")
        recipient = next((opt["value"] for opt in options if opt["name"] == "recipient"), "")
        
        # Handle tip in background thread
        threading.Thread(
            target=self._handle_tip,
            args=(user_id, amount, recipient, payload["token"], payload["application_id"], 
                  body, timestamp, signature)
        ).start()
        
        return jsonify({"type": DISCORD_DEFERRED_RESPONSE_TYPE})

    def health_check(self):
        """Dead-simple health check endpoint"""
        return "OK", 200

    def run(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        """Run the Flask application"""
        self.app.run(host=host, port=port)


if __name__ == "__main__":
    handler = DiscordInteractionHandler()
    handler.run()
