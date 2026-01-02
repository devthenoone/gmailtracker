import streamlit as st
import requests
import urllib.parse
import pandas as pd
from datetime import datetime

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(
    page_title="Email Tracking Dashboard",
    layout="wide"
)

st.title("📧 Email Open & Click Tracking System")

# -----------------------------
# Sidebar – Backend URL
# -----------------------------
st.sidebar.header("⚙️ Configuration")

backend_url = st.sidebar.text_input(
    "Backend URL",
    value="https://YOUR-BACKEND.onrender.com"
)

if backend_url.endswith("/"):
    backend_url = backend_url[:-1]

# -----------------------------
# Helper Functions
# -----------------------------
def build_tracking_image(email, message_id, image_name="2.jpeg"):
    params = {
        "email": email,
        "message_id": message_id,
        "image": image_name
    }
    return f"{backend_url}/api/img?{urllib.parse.urlencode(params)}"


def build_click_link(email, message_id, redirect_url):
    params = {
        "email": email,
        "message_id": message_id,
        "redirect": redirect_url
    }
    return f"{backend_url}/api/click?{urllib.parse.urlencode(params)}"


# -----------------------------
# Email Generator
# -----------------------------
st.header("✉️ Email HTML Generator")

col1, col2 = st.columns(2)

with col1:
    email = st.text_input("Recipient Email", "test@example.com")
    message_id = st.text_input(
        "Message ID",
        f"msg-{int(datetime.utcnow().timestamp())}"
    )

with col2:
    redirect_url = st.text_input(
        "Click Redirect URL",
        "https://example.com"
    )

if st.button("Generate Email HTML"):
    tracking_img = build_tracking_image(email, message_id)
    click_link = build_click_link(email, message_id, redirect_url)

    email_html = f"""
<!DOCTYPE html>
<html>
<body>
    <p>Hello,</p>

    <p>This is a test email with tracking enabled.</p>

    <p>
        <a href="{click_link}" target="_blank">
            👉 Click Here
        </a>
    </p>

    <img src="{tracking_img}" width="1" height="1" style="display:none;" />

    <p>Thank you</p>
</body>
</html>
"""

    st.subheader("📄 Email HTML (Copy & Paste)")
    st.code(email_html, language="html")

# -----------------------------
# Tracking Dashboard
# -----------------------------
st.header("📊 Tracking Dashboard")

tabs = st.tabs(["By Email", "Latest Events"])

# -----------------------------
# Tab 1 – By Email
# -----------------------------
with tabs[0]:
    st.subheader("🔍 Track by Email")

    search_email = st.text_input("Enter email to search")

    if st.button("Fetch Tracking Data"):
        try:
            res = requests.get(
                f"{backend_url}/tracking/by_email",
                params={"email": search_email},
                timeout=10
            )

            if res.status_code == 200:
                data = res.json()

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("📬 Opens", len(data.get("opens", [])))
                with col2:
                    st.metric("🖼️ Image Loads", len(data.get("img_reads", [])))
                with col3:
                    st.metric("🔗 Clicks", len(data.get("clicks", [])))

                if data.get("opens"):
                    st.subheader("📬 Opens")
                    st.dataframe(pd.DataFrame(data["opens"]))

                if data.get("img_reads"):
                    st.subheader("🖼️ Image Loads")
                    st.dataframe(pd.DataFrame(data["img_reads"]))

                if data.get("clicks"):
                    st.subheader("🔗 Clicks")
                    st.dataframe(pd.DataFrame(data["clicks"]))

            else:
                st.error("Failed to fetch data")

        except Exception as e:
            st.error(str(e))

# -----------------------------
# Tab 2 – Latest Events
# -----------------------------
with tabs[1]:
    st.subheader("🕒 Latest Activity")

    if st.button("Refresh Latest Events"):
        try:
            res = requests.get(
                f"{backend_url}/tracking/latest",
                timeout=10
            )

            if res.status_code == 200:
                df = pd.DataFrame(res.json())
                st.dataframe(df)
            else:
                st.error("Failed to fetch latest logs")

        except Exception as e:
            st.error(str(e))

# -----------------------------
# Footer
# -----------------------------
st.markdown("---")
st.caption("🚀 Email Tracking System • Streamlit + FastAPI")
