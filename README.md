# TACo Smart Wallet Reference Implementation

A clean, modular implementation demonstrating how to:
1. Create ETH transfers using account abstraction UserOperation objects
2. Sign UserOperations with TACo threshold signatures via Porter gateway
3. Submit to ERC-4337 bundlers with proper format conversion
4. Integrate with Discord bot commands (smart wallet provider agnostic)

## Architecture

### Core Modules

- **`config.py`**: Configuration and constants
  - `SmartAccountConfig`: Network and API configuration
  - Network constants and default gas limits

- **`user_operations.py`**: UserOperation creation utilities
  - `create_eth_transfer_user_operation()`: ETH transfer UserOp creation
  - Smart wallet execute function encoding

- **`porter.py`**: TACo network gateway service
  - `PorterSignatureService`: Porter gateway integration for TACo signatures
  - Discord context handling and TACo threshold signature aggregation

- **`bundler.py`**: Pimlico bundler integration
  - `BundlerClient`: ERC-4337 bundler communication
  - `convert_user_operation_to_pimlico_format()`: Format conversion

- **`smart_account.py`**: Main service orchestration
  - `TacoSmartWalletService`: High-level ETH transfer operations
  - Gas optimization and balance validation

- **`app.py`**: Discord bot implementation
  - Signature verification and command handling
  - Background thread processing for async operations
  - Clean error handling and response formatting

## Quick Start

### Option 1: Local Development

1. **Environment Setup**
   ```bash
   export PIMLICO_API_KEY="your_pimlico_api_key"
   export DISCORD_BOT_PUBLIC_KEY="your_discord_bot_public_key"
   ```

2. **Installation**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Bot**
   ```bash
   python app.py
   ```

### Option 2: Docker Compose

1. **Environment Setup**
   Create a `.env` file in the project root:
   ```bash
   # TACo Smart Wallet Configuration
   PIMLICO_API_KEY=your_pimlico_api_key_here
   DISCORD_BOT_PUBLIC_KEY=your_discord_bot_public_key_here
   
   # Discord Command Sync Configuration (for syncing slash commands)
   DISCORD_APPLICATION_ID=your_discord_application_id_here
   DISCORD_BOT_TOKEN=your_discord_bot_token_here
   ```

2. **Run with Docker Compose**
   ```bash
   docker-compose up --build
   ```

   The bot will be available at `http://localhost:8080` with a health check at `/health`

### Discord Command Sync

To sync slash commands with Discord (required for first-time setup or when commands change):

```bash
python sync_commands.py
```

This requires `DISCORD_APPLICATION_ID` and `DISCORD_BOT_TOKEN` environment variables.

### Discord Bot
- Slash command: `/tip <amount> <recipient>`
- Background processing to avoid Discord timeouts
- Clean error messages and transaction feedback

## Technical Details

### Network Configuration
- **Network**: Base Sepolia (Chain ID: 84532)
- **EntryPoint**: `0x0000000071727De22E5E9d8BAf0edAc6f37da032`
- **Smart Wallet**: `0xBF151420A84A6Bb7b1213d8269a5F1fe43FC3276` (example - works with any ERC-4337 wallet)

### TACo Network Configuration
- **Porter Gateway**: `https://porter-lynx.nucypher.io`
- **Cohort ID**: 2 (Lynx domain)
- **Threshold**: 2 TACo signatures required

## Example Flow

1. User runs `/tip 0.01 @friend` in Discord
2. Discord signature verified and user ID extracted
3. Tip parameters parsed and validated
4. UserOperation created for ETH transfer
5. TACo network signs with threshold signatures (2/3 nodes) via Porter gateway
6. Bundler submits to Base Sepolia network
7. Transaction hash returned to Discord channel
