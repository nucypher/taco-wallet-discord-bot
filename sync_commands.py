import requests
import os

# Discord application credentials from environment variables
APPLICATION_ID = os.environ.get("DISCORD_APPLICATION_ID")
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

if not APPLICATION_ID:
    raise ValueError("DISCORD_APPLICATION_ID environment variable is required")
if not BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable is required")

# The command definition
commands = [
    {
        "name": "tip",
        "description": "Send ETH from your Smart Account using threshold signatures",
        "options": [
            {
                "name": "amount",
                "description": "Amount of ETH to send (e.g., 0.01)",
                "type": 3,  # STRING type
                "required": True,
            },
            {
                "name": "recipient",
                "description": "Recipient user or wallet address (e.g., @username or 0x...)",
                "type": 3,  # STRING type
                "required": True,
            },
        ],
    },
    {
        "name": "address",
        "description": "Get the smart account address for a user",
        "options": [
            {
                "name": "user",
                "description": "The user to get the address for (e.g., @username)",
                "type": 6,  # USER type
                "required": True,
            }
        ],
    },
]


def sync_commands():
    # Discord API endpoint for application commands
    url = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"

    # Headers required for authentication
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}

    try:
        # Send the request to Discord
        response = requests.put(url, headers=headers, json=commands)
        response.raise_for_status()

        # Print the response
        print("Successfully synced commands:")
        for cmd in response.json():
            print(f"- /{cmd['name']}: {cmd['description']}")

    except requests.exceptions.RequestException as e:
        print(f"Error syncing commands: {e}")
        if hasattr(e.response, "text"):
            print(f"Response: {e.response.text}")


if __name__ == "__main__":
    sync_commands()
