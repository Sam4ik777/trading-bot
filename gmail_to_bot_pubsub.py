import os
import base64
import email
import json
import re
import time
import logging
import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.cloud import pubsub_v1
from google.oauth2 import service_account

# ---------------- CONFIG ----------------
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
PROJECT_ID = os.getenv("PROJECT_ID", "trading-bot-478222")
TOPIC_NAME = f"projects/{PROJECT_ID}/topics/gmail-alerts"
SUBSCRIPTION_NAME = f"projects/{PROJECT_ID}/subscriptions/gmail-alerts-sub"
NGROK_URL = os.getenv("BOT_WEBHOOK_URL", "https://your-ngrok-url/webhook")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", r"C:\path\to\service_account.json")

WATCH_RENEW_INTERVAL = 50 * 60  # Renew Gmail watch every 50 minutes

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------------- AUTH ----------------
def gmail_authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

# ---------------- GMAIL WATCH ----------------
def start_watch(service):
    try:
        logging.info("Starting Gmail watch...")
        service.users().watch(
            userId='me',
            body={
                'topicName': TOPIC_NAME,
                'labelIds': ['INBOX']
            }
        ).execute()
        logging.info("Gmail watch started successfully.")
    except Exception as e:
        logging.error(f"Failed to start Gmail watch: {e}")

# ---------------- EMAIL PARSING ----------------
def extract_signal(body):
    # Improved regex based on expected email format
    signal_match = re.search(r'\b(BUY|SELL)\b', body.upper())
    re.search(r'Symbol:\s*([A-Z]{1,5})', body)
    price_match = re.search(r'Price:\s*(\d+\.\d+)', body)

    signal = signal_match.group(0) if signal_match else None
    symbol = symbol_match.group(1) if symbol_match else None
    price = float(price_match.group(1)) if price_match else 0.0

    return signal, symbol, price

def fetch_email(service, msg_id):
    try:
        msg = service.users().messages().get(userId='me', id=msg_id, format='raw').execute()
        raw_msg = base64.urlsafe_b64decode(msg['raw'].encode('ASCII'))
        mime_msg = email.message_from_bytes(raw_msg)
        return mime_msg.get_payload()
    except Exception as e:
        logging.error(f"Error fetching email: {e}")
        return ""

# ---------------- HISTORY HANDLER ----------------
def get_new_message_ids(service, history_id):
    try:
        history = service.users().history().list(
            userId='me',
            startHistoryId=history_id,
            historyTypes=['messageAdded']
        ).execute()
        message_ids = []
        if 'history' in history:
            for record in history['history']:
                if 'messagesAdded' in record:
                    for msg in record['messagesAdded']:
                        message_ids.append(msg['message']['id'])
        return message_ids
    except Exception as e:
        logging.error(f"Error fetching history: {e}")
        return []

# ---------------- SEND TO BOT ----------------
def send_to_bot(signal, symbol, price):
    if not signal or not symbol or price <= 0:
        logging.warning(f"Invalid trade data: signal={signal}, symbol={symbol}, price={price}")
        return
    payload = {"signal": signal, "symbol": symbol, "price": price}
    try:
        response = requests.post(NGROK_URL, json=payload, timeout=10)
        logging.info(f"Sent to bot: {payload}, Response: {response.status_code} {response.text}")
    except Exception as e:
        logging.error(f"Error sending to bot: {e}")

# ---------------- PUB/SUB LISTENER ----------------
def listen_pubsub(service):
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"Service account file not found at {SERVICE_ACCOUNT_FILE}. Please verify the filename and location.")

    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
    subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
    subscription_path = SUBSCRIPTION_NAME

    def callback(message):
        try:
            data = json.loads(message.data.decode('utf-8'))
            history_id = data.get('historyId')
            logging.info(f"Received Pub/Sub message: historyId={history_id}")
            if history_id:
                message_ids = get_new_message_ids(service, history_id)
                for msg_id in message_ids:
                    body = fetch_email(service, msg_id)
                    signal, symbol, price = extract_signal(body)
                    if signal:
                        send_to_bot(signal, symbol, price)
            message.ack()
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            message.ack()

    subscriber.subscribe(subscription_path, callback=callback)
    logging.info("Listening for Gmail alerts via Pub/Sub...")

    # Keep alive loop
    while True:
        time.sleep(1)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    service = gmail_authenticate()
    start_watch(service)

    # Renew Gmail watch periodically
    last_watch_time = time.time()

    # Run Pub/Sub listener in main thread
    while True:
        listen_pubsub(service)
        # Renew watch if interval passed
        if time.time() - last_watch_time > WATCH_RENEW_INTERVAL:
            start_watch(service)
