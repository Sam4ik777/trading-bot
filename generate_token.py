from google_auth_oauthlib.flow import InstalledAppFlow

# Correct scope for your bot
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def main():
    # Make sure credentials.json is in the same folder
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)

    # Save token.json locally
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
    print("✅ Token generated and saved to token.json")

if __name__ == "__main__":
    main()