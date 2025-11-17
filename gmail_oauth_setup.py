import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def gmail_authenticate():
    # Load token from environment variable
    token_json = os.getenv("GMAIL_TOKEN")
    if not token_json:
        raise ValueError("GMAIL_TOKEN environment variable is missing.")
    
    creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    return build('gmail', 'v1', credentials=creds)

# Example usage
if __name__ == "__main__":
    service = gmail_authenticate()
    results = service.users().messages().list(userId='me', q="is:unread", maxResults=5).execute()
    messages = results.get('messages', [])
    print(f"Found {len(messages)} unread messages.")