# auth_gmail.py
import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email"
]

TOKENS_DIR = "tokens"


def get_gmail_service():
    os.makedirs(TOKENS_DIR, exist_ok=True)

    creds = None
    email_address = None

    # Try existing tokens
    for user_folder in os.listdir(TOKENS_DIR):
        token_path = os.path.join(TOKENS_DIR, user_folder, "token.json")
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            if creds and creds.valid:
                email_address = user_folder
                break
            elif creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                email_address = user_folder
                break
            else:
                creds = None

    # OAuth if no valid token
    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            SCOPES
        )
        creds = flow.run_local_server(port=0)

        oauth2_service = build("oauth2", "v2", credentials=creds)
        user_info = oauth2_service.userinfo().get().execute()
        email_address = user_info["email"]

        user_dir = os.path.join(TOKENS_DIR, email_address)
        os.makedirs(user_dir, exist_ok=True)

        with open(os.path.join(user_dir, "token.json"), "w") as f:
            f.write(creds.to_json())

    gmail_service = build("gmail", "v1", credentials=creds)
    return gmail_service, email_address


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
