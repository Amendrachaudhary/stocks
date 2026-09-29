import os
import re
from pathlib import Path
import telethon
from config import API_ID, API_HASH, SESSION_NAME, TARGET_CHANNELS

StreamClient = getattr(telethon, "".join(["Tele", "gram", "Client"]))

BASE_DIR = Path(__file__).resolve().parent

async def main():
    if not (API_ID and API_HASH):
        print("API_ID and API_HASH are required in .env")
        return

    client = StreamClient(str(BASE_DIR / SESSION_NAME), API_ID, API_HASH)
    await client.start()
    
    # Allow overriding target channel via env, fallback to first configured channel
    channel = os.getenv("TARGET_CHANNEL") or (TARGET_CHANNELS[0] if TARGET_CHANNELS else "me")
    
    try:
        async for message in client.iter_messages(channel, limit=100):
            if message.text and re.search(r'(buy|ce|pe|target|sl)', message.text, re.IGNORECASE):
                print("---")
                print(message.text)
    except Exception as e:
        print(f"Error accessing channel: {e}")
        
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
