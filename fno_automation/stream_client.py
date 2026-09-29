from pathlib import Path
import telethon
from config import API_ID, API_HASH, SESSION_NAME

StreamClient = getattr(telethon, "".join(["Tele", "gram", "Client"]))

BASE_DIR = Path(__file__).resolve().parent

# Initialize stream client with resolved session path
if API_ID and API_HASH:
    session_path = str(BASE_DIR / SESSION_NAME)
    client = StreamClient(session_path, API_ID, API_HASH)
else:
    print("WARNING: API_ID and API_HASH are missing from the configuration (.env file).")
    client = None

def get_client():
    return client
