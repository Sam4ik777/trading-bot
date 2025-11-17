from __future__ import print_function
import os.path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import json

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def main():
    creds = None
    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists('token.json'):
        with open('token.json', 'r') as token:
            creds_data = json.load(token)
            # You can optionally validate creds_data here
    # If there are no valid credentials, let the user log in.
    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        # Use local server flow to avoid redirect_uri issues
        creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    print("Token generated successfully and saved to token.json")

if __name__ == '__main__':
    main()