# auth_gmail.py
import os
import json
import streamlit as st
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify"
]

TOKENS_DIR = "tokens"


def get_gmail_service():
    os.makedirs(TOKENS_DIR, exist_ok=True)

    creds = None
    sender_email = None

    # -------------------------------------------
    # 1️⃣ Try existing tokens
    # -------------------------------------------
    for user_folder in os.listdir(TOKENS_DIR):
        token_path = os.path.join(TOKENS_DIR, user_folder, "token.json")
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            if creds and creds.valid:
                sender_email = user_folder
                break
            elif creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                sender_email = user_folder
                break
            else:
                creds = None

    # -------------------------------------------
    # 2️⃣ OAuth flow (FIRST TIME)
    # -------------------------------------------
    if not creds:
        # 🔥 WRITE credentials.json FROM STREAMLIT SECRETS
        client_config = {
            "installed": {
                "client_id": st.secrets["gmail"]["client_id"],
                "client_secret": st.secrets["gmail"]["client_secret"],
                "auth_uri": st.secrets["gmail"]["auth_uri"],
                "token_uri": st.secrets["gmail"]["token_uri"],
                "redirect_uris": st.secrets["gmail"]["redirect_uris"]
            }
        }

        with open("credentials_temp.json", "w") as f:
            json.dump(client_config, f)

        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials_temp.json",
            SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Get sender email
        oauth2_service = build("oauth2", "v2", credentials=creds)
        user_info = oauth2_service.userinfo().get().execute()
        sender_email = user_info["email"]

        # Save token per user
        user_dir = os.path.join(TOKENS_DIR, sender_email)
        os.makedirs(user_dir, exist_ok=True)

        with open(os.path.join(user_dir, "token.json"), "w") as f:
            f.write(creds.to_json())

        os.remove("credentials_temp.json")

    # -------------------------------------------
    # 3️⃣ Return Gmail service + sender
    # -------------------------------------------
    service = build("gmail", "v1", credentials=creds)
    return service, sender_email




# # auth_gmail.py
# import os
# from google.oauth2.credentials import Credentials
# from googleapiclient.discovery import build
# from google.auth.transport.requests import Request

# SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# def get_gmail_service():
#     creds = Credentials(
#         token=os.getenv("GOOGLE_ACCESS_TOKEN"),
#         refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
#         token_uri=os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
#         client_id=os.getenv("GOOGLE_CLIENT_ID"),
#         client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
#         scopes=SCOPES,
#     )

#     # Auto-refresh expired token
#     if creds.expired and creds.refresh_token:
#         creds.refresh(Request())

#     return build("gmail", "v1", credentials=creds)
