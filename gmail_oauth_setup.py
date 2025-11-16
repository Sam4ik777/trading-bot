import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Load token from Render environment variable
token_json = os.getenv("GMAIL_TOKEN")  # This is the variable you added in Render
creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)

# Build Gmail API service
service = build('gmail', 'v1', credentials=creds)

# Example: List messages
results = service.users().messages().list(userId='me').execute()
messages = results.get('messages', [])
print(f"Found {len(messages)} messages.")