import streamlit as st
import requests
import pandas as pd
import urllib.parse
import base64
import matplotlib.pyplot as plt
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import re
import dns.resolver

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(page_title="Email Tracker", layout="wide")

backend_url = st.sidebar.text_input(
    "Backend URL",
    "https://gmailtracker-3mia.onrender.com"
).rstrip("/")

st.sidebar.markdown("### Tracking Enabled")
st.sidebar.write("- Sent")
st.sidebar.write("- Read (open OR click)")
st.sidebar.write("- Not delivered")
st.sidebar.write("- Derived not opened")

# =========================================================
# HELPERS
# =========================================================
def tracking_img_url(email, message_id, image=None):
    params = {"email": email, "message_id": message_id}
    if image:
        params["image"] = image
    return f"{backend_url}/api/img?{urllib.parse.urlencode(params)}"

def tracking_click_url(email, target, message_id):
    params = {"email": email, "redirect": target, "message_id": message_id}
    return f"{backend_url}/api/click?{urllib.parse.urlencode(params)}"

EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

def verify_email(email):
    if not EMAIL_REGEX.match(email):
        return False, "Invalid format"
    try:
        dns.resolver.resolve(email.split("@")[1], "MX")
        return True, "Valid"
    except Exception:
        return False, "No MX record"

# =========================================================
# COMPOSE EMAIL
# =========================================================
st.subheader("📨 Compose Tracked Email")

c1, c2 = st.columns(2)

with c1:
    to_raw = st.text_input("Recipient Emails", "a@gmail.com, b@gmail.com")
    subject = st.text_input("Subject", "You received 500 yield points")
    message = st.text_area("Message", "Expires on 30 April 2025")
    campaign_id = st.text_input("Campaign ID", "yield-001")

with c2:
    cta_label = st.text_input("CTA Button Text", "Redeem")
    cta_url = st.text_input("CTA URL", "https://aizensol.com")
    signature_image = st.selectbox(
        "Signature Image",
        ["welcome/banner.png", "welcome/images.png"]
    )

# =========================================================
# SEND EMAILS
# =========================================================
st.subheader("📤 Send via Gmail")

from auth_gmail import get_gmail_service  # ← uses st.secrets["gmail"]

if st.button("Send Emails"):
    try:
        gmail_service, sender_email = get_gmail_service()
    except Exception as e:
        st.error("Failed to authenticate Gmail")
        st.exception(e)
        st.stop()

    raw_emails = [e.strip() for e in to_raw.split(",") if e.strip()]
    valid, invalid = [], []

    for e in raw_emails:
        ok, reason = verify_email(e)
        (valid if ok else invalid).append((e, reason))

    if invalid:
        st.warning("Invalid emails skipped:")
        for e, r in invalid:
            st.write(f"❌ {e} — {r}")

    if not valid:
        st.error("No valid emails to send.")
        st.stop()

    sent, not_delivered = 0, 0

    for idx, (email, _) in enumerate(valid, start=1):
        message_id = f"{campaign_id}-{idx}"

        try:
            click_url = tracking_click_url(email, cta_url, message_id)
            pixel_url = tracking_img_url(email, message_id)
            sig_url = tracking_img_url(email, message_id, signature_image)

            html = f"""
            <html><body>
            <table width="600" style="background:#8b7cf6;color:white;padding:32px;border-radius:22px">
              <tr>
                <td width="70%">
                  <h2>{subject}</h2>
                  <p>{message}</p>
                  <a href="{click_url}" style="background:white;color:#6a5af9;
                     padding:12px 28px;border-radius:20px;text-decoration:none;">
                     {cta_label}
                  </a>
                </td>
                <td width="30%" align="right">
                  <img src="{sig_url}" width="120">
                </td>
              </tr>
            </table>
            <img src="{pixel_url}" width="1" height="1">
            </body></html>
            """

            msg = MIMEMultipart("alternative")
            msg["to"] = email
            msg["subject"] = subject
            msg.attach(MIMEText("Fallback", "plain"))
            msg.attach(MIMEText(html, "html"))

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

            gmail_service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()

            requests.post(
                f"{backend_url}/api/sent",
                params={
                    "email": email,
                    "message_id": message_id,
                    "sender": sender_email
                }
            )

            sent += 1

        except Exception as e:
            not_delivered += 1
            requests.post(
                f"{backend_url}/api/not-delivered",
                params={
                    "email": email,
                    "message_id": message_id,
                    "sender": sender_email
                }
            )

    st.success(f"Sender: {sender_email} | Sent: {sent} | Not Delivered: {not_delivered}")

# =========================================================
# DELIVERY FUNNEL CHART
# =========================================================
st.subheader("📊 Email Delivery Funnel")

if st.button("Show Delivery Chart"):
    events = requests.get(f"{backend_url}/tracking/all").json()["events"]

    sent = {e["email"] for e in events if e["type"] == "sent"}
    read = {e["email"] for e in events if e["type"] == "read"}
    not_delivered = {e["email"] for e in events if e["type"] == "not_delivered"}

    not_opened = max(len(sent) - len(read) - len(not_delivered), 0)

    labels = ["Sent", "Read", "Not Opened", "Responded", "Not Delivered"]
    values = [len(sent), len(read), not_opened, 0, len(not_delivered)]

    fig, ax = plt.subplots(figsize=(9, 4))
    bars = ax.bar(labels, values)
    ax.set_title("Email Engagement Funnel")

    for b in bars:
        ax.text(
            b.get_x() + b.get_width() / 2,
            b.get_height() + 0.1,
            int(b.get_height()),
            ha="center"
        )

    st.pyplot(fig)

# =========================================================
# FETCH ALL LOG DATA
# =========================================================
st.subheader("📦 Fetch ALL Logs")

if st.button("Fetch ALL Tracking Data"):
    res = requests.get(f"{backend_url}/tracking/all", timeout=10)
    all_data = res.json()

    for key in ["events", "opens", "clicks", "img_reads"]:
        df = pd.DataFrame(all_data.get(key, []))
        if not df.empty:
            df["time"] = pd.to_datetime(df["time"])
            st.markdown(f"### {key.title()}")
            st.dataframe(df.sort_values("time", ascending=False))


# # streamlit_app.py
# import os
# import streamlit as st
# import requests
# import pandas as pd
# import urllib.parse
# import base64
# import matplotlib.pyplot as plt

# # -------------------------
# # Backend URL
# # -------------------------
# backend_url = st.sidebar.text_input("Backend URL", value="https://gmailtracker-3mia.onrender.com")
# backend_url = backend_url.rstrip("/")

# st.sidebar.markdown("### What is tracked?")
# st.sidebar.write("- Email opens (pixel load)")
# st.sidebar.write("- Image loads (local or remote)")
# st.sidebar.write("- Link clicks")
# st.sidebar.write("- User agent & IP logs")

# # -------------------------
# # Helper functions
# # -------------------------
# def tracking_img_url(email, message_id=None, image_param=None):
#     params = {"email": email}
#     if message_id:
#         params["message_id"] = message_id
#     if image_param:
#         params["image"] = image_param
#     qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote_plus)
#     return f"{backend_url}/api/img?{qs}"

# def tracking_click_url(email, target, message_id=None):
#     params = {"email": email, "redirect": target}
#     if message_id:
#         params["message_id"] = message_id
#     qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote_plus)
#     return f"{backend_url}/api/click?{qs}"

# # -------------------------
# # HTML Builder
# # -------------------------
# st.subheader("Generate HTML for Your Email")

# col1, col2 = st.columns(2)
# with col1:
#     to = st.text_input("Recipient Email")
#     subject = st.text_input("Subject", value="Tracked Email")
#     message_id = st.text_input("Message ID (optional)", "mid-001")

# with col2:
#     visible_image = st.text_input("Image URL OR local filename (optional)")
#     link_target = st.text_input("Tracked Link URL", value="https://aizensol.com")
#     signature_image = st.text_input("Signature Image Filename (e.g., 2.jpeg)", value="2.jpeg")

# if st.button("Generate HTML Snippet"):
#     if not to:
#         st.error("Recipient email required!")
#     else:
#         visible_img_url = tracking_img_url(to, message_id, visible_image or None)
#         click_url = tracking_click_url(to, link_target, message_id)
#         pixel_only_url = tracking_img_url(to, message_id, None)
#         signature_img_url = tracking_img_url(to, message_id, signature_image or "2.jpeg")

#         html = f"""
# <!DOCTYPE HTML>
# <html>
# <body style="font-size: 10pt; font-family: Arial, sans-serif;">
# <p>Hello, this is your tracked email.</p>
# <img src="{visible_img_url}" width="200" height="200" alt="Image"><br><br>
# <a href="{click_url}">Click this tracked link</a>
# <img src="{pixel_only_url}" width="1" height="1" style="display:none;" />
# </body>
# </html>
# """
#         # Save HTML to session_state so it persists
#         st.session_state["html"] = html

#         st.code(html, language="html")
#         st.success("HTML generated successfully! Paste this in your email (HTML mode).")

# # -------------------------
# # Gmail Sending (optional)
# # -------------------------
# try:
#     from auth_gmail import get_gmail_service
#     gmail_service = get_gmail_service()
#     gmail_ready = True
# except Exception:
#     gmail_service = None
#     gmail_ready = False

# if gmail_ready:
#     st.subheader("Send Test Email via Gmail API")
#     if st.button("Send Email via Gmail"):
#         if not to:
#             st.error("Recipient email required!")
#         elif "html" not in st.session_state:
#             st.error("Generate the HTML snippet first!")
#         else:
#             html = st.session_state["html"]
#             try:
#                 from email.mime.multipart import MIMEMultipart
#                 from email.mime.text import MIMEText

#                 msg = MIMEMultipart("alternative")
#                 msg["to"] = to
#                 msg["subject"] = subject
#                 msg.attach(MIMEText("Plain text fallback", "plain"))
#                 msg.attach(MIMEText(html, "html"))

#                 encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
#                 res = gmail_service.users().messages().send(
#                     userId="me", body={"raw": encoded}
#                 ).execute()

#                 st.success("Email sent successfully!")
#                 st.json(res)
#             except Exception as e:
#                 st.error(f"Sending failed: {e}")
# else:
#     st.info("Gmail sending not enabled. Add auth_gmail.py to enable sending.")

# # -------------------------
# # Tracking Logs
# # -------------------------
# st.subheader("📊 Tracking Logs")
# email_query = st.text_input("Search events by email")

# # Initialize data safely
# data = {}

# if st.button("Fetch Email Activity"):
#     if not email_query:
#         st.error("Enter an email to fetch activity!")
#     else:
#         try:
#             res = requests.get(f"{backend_url}/tracking/by_email", params={"email": email_query}, timeout=10)
#             data = res.json()

#             open_count = len(data.get("opens", []))
#             click_count = len(data.get("clicks", []))
#             img_read_count = len(data.get("img_reads", []))

#             st.markdown(f"### 📌 Summary for **{email_query}**")
#             st.write(f"**Opens:** {open_count}")
#             st.write(f"**Link Clicks:** {click_count}")
#             st.write(f"**Image Loads:** {img_read_count}")

#             # Show detailed tables
#             for key in ["opens", "img_reads", "clicks"]:
#                 df = pd.DataFrame(data.get(key, []))
#                 if not df.empty:
#                     df["time"] = pd.to_datetime(df["time"])
#                     df = df.sort_values("time", ascending=False)
#                     st.markdown(f"### {key.replace('_', ' ').title()}")
#                     st.dataframe(df)
#         except Exception as e:
#             st.error(f"Request failed: {e}")

# if st.button("Refresh Latest Logs"):
#     try:
#         res = requests.get(f"{backend_url}/tracking/latest", timeout=10)
#         data = res.json()
#         st.markdown("### Latest Events")
#         st.dataframe(pd.DataFrame(data.get("events", [])))
#         st.markdown("### Latest Image Reads")
#         st.dataframe(pd.DataFrame(data.get("img_reads", [])))
#     except Exception as e:
#         st.error(f"Failed to load logs: {e}")

# st.markdown("---")
# st.markdown("This dashboard works with the updated FastAPI backend and supports open, click, and image tracking.")

# # -------------------------
# # EMAIL ENGAGEMENT ANALYTICS
# # -------------------------
# st.subheader("📊 Email Engagement Analytics")

# if st.button("Show Email Engagement Analytics"):
#     if not email_query:
#         st.error("Enter an email above to fetch engagement data first!")
#     else:
#         try:
#             res = requests.get(f"{backend_url}/tracking/by_email", params={"email": email_query}, timeout=10)
#             data = res.json()

#             opens = data.get("opens", [])
#             clicks = data.get("clicks", [])
#             delivered = 1  # Assuming 1 email sent

#             opened = len({o["message_id"] for o in opens if o.get("message_id")})
#             clicked = len({c["message_id"] for c in clicks if c.get("message_id")})
#             not_opened = max(delivered - opened, 0)

#             labels = ["Delivered", "Opened", "Not Opened", "Clicked"]
#             values = [delivered, opened, not_opened, clicked]

#             fig, ax = plt.subplots()
#             ax.bar(labels, values, color=["gray", "green", "red", "blue"])
#             ax.set_ylabel("Count")
#             ax.set_title(f"Email Engagement Summary for {email_query}")
#             st.pyplot(fig)
#         except Exception as e:
#             st.error(f"Failed to fetch analytics: {e}")

# st.subheader("📊 All Emails Activity")

# if st.button("Fetch All Emails Data"):
#     try:
#         res = requests.get(f"{backend_url}/tracking/all", timeout=10)  # Make sure your backend has this endpoint
#         all_data = res.json()

#         # Example keys: events, opens, clicks, img_reads
#         for key in ["events", "opens", "clicks", "img_reads"]:
#             df = pd.DataFrame(all_data.get(key, []))
#             if not df.empty:
#                 df["time"] = pd.to_datetime(df["time"])
#                 df = df.sort_values("time", ascending=False)
#                 st.markdown(f"### {key.replace('_', ' ').title()}")
#                 st.dataframe(df)
#             else:
#                 st.write(f"No {key} data available.")
#     except Exception as e:
#         st.error(f"Failed to fetch all emails data: {e}")


# if st.button("Show Overall Email Analytics"):
#     try:
#         res = requests.get(f"{backend_url}/tracking/all", timeout=10)
#         all_data = res.json()

#         total_emails = len({e["email"] for e in all_data.get("events", [])})
#         total_opens = len(all_data.get("opens", []))
#         total_clicks = len(all_data.get("clicks", []))
#         total_img_reads = len(all_data.get("img_reads", []))

#         labels = ["Total Emails", "Opens", "Clicks", "Image Loads"]
#         values = [total_emails, total_opens, total_clicks, total_img_reads]

#         fig, ax = plt.subplots()
#         ax.bar(labels, values, color=["gray", "green", "blue", "orange"])
#         ax.set_ylabel("Count")
#         ax.set_title("Overall Email Engagement Summary")
#         st.pyplot(fig)
#     except Exception as e:
#         st.error(f"Failed to fetch overall analytics: {e}")
