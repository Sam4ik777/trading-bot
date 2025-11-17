import os
import base64
import email
import re
import time
import logging
import requests
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ---------------- CONFIG ----------------
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']  # Allows read + mark as read
CHECK_INTERVAL = 30  # seconds between Gmail checks
WEBHOOK_URL = os.getenv("BOT_WEBHOOK_URL", "https://your-render-flask-service.onrender.com/webhook")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------------- AUTH ----------------
def gmail_authenticate():
    token_json = os.getenv("GMAIL_TOKEN")
    if not token_json:
        # Fallback to token.json file for local testing
        try:
            with open("token.json", "r") as f:
                token_json = f.read()
            logging.info("Loaded token from token.json file.")
        except FileNotFoundError:
            raise ValueError("GMAIL_TOKEN environment variable is missing and token.json file not found.")
    
    # Parse token and remove expiry to avoid parsing errors
    token_data = json.loads(token_json)
    token_data.pop("expiry", None)  # Remove expiry if present

    creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    return build('gmail', 'v1', credentials=creds)

# ---------------- EMAIL PARSING ----------------
def extract_signal(body):
    logging.info(f"Email body:\n{body}")
    signal_match = re.search(r'\b(BUY|SELL)\b', body.upper())
    symbol_match = re.search(r'(?:Symbol:\s*)?([A-Z]{1,6})', body)
    price_match = re.search(r'(?:Price:\s*)?(\d+\.\d+)', body)

    signal = signal_match.group(0) if signal_match else None
    symbol = symbol_match.group(1) if symbol_match else None
    price = float(price_match.group(1)) if price_match else 0.0

    return signal, symbol, price

# ---------------- FETCH EMAIL ----------------
def fetch_email(service, msg_id):
    try:
        msg = service.users().messages().get(userId='me', id=msg_id, format='raw').execute()
        raw_msg = base64.urlsafe_b64decode(msg['raw'].encode('ASCII'))
        mime_msg = email.message_from_bytes(raw_msg)

        if mime_msg.is_multipart():
            parts = mime_msg.get_payload()
            body = ""
            for part in parts:
                if part.get_content_type() == "text/plain":
                    body += part.get_payload()
        else:
            body = mime_msg.get_payload()

        return body
    except Exception as e:
        logging.error(f"Error fetching email: {e}")
        return ""

# ---------------- SEND TO BOT ----------------
def send_to_bot(signal, symbol, price):
    if not signal or not symbol or price <= 0:
        logging.warning(f"Invalid trade data: signal={signal}, symbol={symbol}, price={price}")
        return
    payload = {"signal": signal, "symbol": symbol, "price": price}
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        logging.info(f"Sent to bot: {payload}, Response: {response.status_code} {response.text}")
    except Exception as e:
        logging.error(f"Error sending to bot: {e}")

# ---------------- MAIN LOOP ----------------
def main():
    service = gmail_authenticate()
    last_checked_id = None

    while True:
        try:
            results = service.users().messages().list(userId='me', labelIds=['INBOX'], q="is:unread", maxResults=5).execute()
            messages = results.get('messages', [])

            for msg in messages:
                msg_id = msg['id']
                if msg_id != last_checked_id:
                    body = fetch_email(service, msg_id)
                    signal, symbol, price = extract_signal(body)
                    if signal:
                        send_to_bot(signal, symbol, price)
                    service.users().messages().modify(userId='me', id=msg_id, body={'removeLabelIds': ['UNREAD']}).execute()
                    last_checked_id = msg_id

            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()