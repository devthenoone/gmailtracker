import streamlit as st
import os
import json
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def get_gmail_service():
    gmail_secrets = st.secrets["gmail"]

    client_config = {
        "installed": {
            "client_id": gmail_secrets["client_id"],
            "client_secret": gmail_secrets["client_secret"],
            "auth_uri": gmail_secrets["auth_uri"],
            "token_uri": gmail_secrets["token_uri"],
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"]
        }
    }

    # Session token reuse
    if "gmail_token" in st.session_state:
        creds = Credentials.from_authorized_user_info(
            st.session_state["gmail_token"], SCOPES
        )
    else:
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob"
        )

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent"
        )

        st.info("🔐 Authenticate Gmail")
        st.markdown(f"[Click here to login with Google]({auth_url})")

        auth_code = st.text_input("Paste authorization code here")

        if not auth_code:
            st.stop()

        flow.fetch_token(code=auth_code)
        creds = flow.credentials

        st.session_state["gmail_token"] = json.loads(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    sender_email = service.users().getProfile(userId="me").execute()["emailAddress"]

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
