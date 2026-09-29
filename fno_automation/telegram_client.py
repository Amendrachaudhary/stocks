from pathlib import Path
from telethon import TelegramClient
from config import API_ID, API_HASH, SESSION_NAME

BASE_DIR = Path(__file__).resolve().parent

# Initialize Telegram client with resolved session path
if API_ID and API_HASH:
    session_path = str(BASE_DIR / SESSION_NAME)
    client = TelegramClient(session_path, API_ID, API_HASH)
else:
    print("WARNING: API_ID and API_HASH are missing from the configuration (.env file).")
    client = None

def get_client():
    return client
