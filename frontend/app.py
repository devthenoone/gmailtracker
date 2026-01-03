# streamlit_app.py
import os
import streamlit as st
import requests
import pandas as pd
import urllib.parse
import base64

st.set_page_config(page_title="Email Tracker Dashboard", layout="wide")
st.title("📧 Email Tracking Dashboard (File-Based System)")

# -------------------------
# Backend URL
# -------------------------
backend_url = st.sidebar.text_input("Backend URL", value="http://localhost:8000")
if not backend_url.endswith("/"):
    backend_url = backend_url.rstrip("/")

st.sidebar.markdown("### What is tracked?")
st.sidebar.write("- Email opens (pixel load)")
st.sidebar.write("- Image loads (local or remote)")
st.sidebar.write("- Link clicks")
st.sidebar.write("- User agent & IP logs")

# -------------------------
# Helper functions
# -------------------------
def tracking_img_url(email, message_id=None, image_param=None):
    params = {"email": email}
    if message_id:
        params["message_id"] = message_id
    if image_param:
        params["image"] = image_param
    qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote_plus)
    return f"{backend_url}/api/img?{qs}"

def tracking_click_url(email, target, message_id=None):
    params = {"email": email, "redirect": target}
    if message_id:
        params["message_id"] = message_id
    qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote_plus)
    return f"{backend_url}/api/click?{qs}"

# -------------------------
# HTML Builder
# -------------------------
st.subheader("Generate HTML for Your Email")

col1, col2 = st.columns(2)
with col1:
    to = st.text_input("Recipient Email")
    subject = st.text_input("Subject", value="Tracked Email")
    message_id = st.text_input("Message ID (optional)", "mid-001")

with col2:
    visible_image = st.text_input("Image URL OR local filename (optional)")
    link_target = st.text_input("Tracked Link URL", value="https://aizensol.com")
    signature_image = st.text_input("Signature Image Filename (e.g., 2.jpeg)", value="2.jpeg")

if st.button("Generate HTML Snippet"):
    if not to:
        st.error("Recipient email required!")
    else:
        visible_img_url = tracking_img_url(to, message_id, visible_image or None)
        click_url = tracking_click_url(to, link_target, message_id)
        pixel_only_url = tracking_img_url(to, message_id, None)
        signature_img_url = tracking_img_url(to, message_id, signature_image or "2.jpeg")

        html = f"""
<!DOCTYPE HTML>
<html>
<body style="font-size: 10pt; font-family: Arial, sans-serif;">

<p>Hello, this is your tracked email.</p>

<!-- Main visible image -->
<img src="{visible_img_url}" width="200" height="200" alt="Image"><br><br>

<!-- Tracked link -->
<a href="{click_url}">Click this tracked link</a>

<!-- Invisible 1x1 tracking pixel -->
<img src="{pixel_only_url}" width="1" height="1" style="display:none;" />

<br><br>
<!-- ================= SIGNATURE START ================= -->

<table cellspacing="0" cellpadding="0" border="0" 
       style="COLOR:#000; font-family:Arial; width:500px; background: transparent;">
<tbody>
<tr>

<td style="text-align:center;border: 2px solid #000; width:197px">
    <!-- VISIBLE signature logo 500x500 -->
    <img style="width:200px; height:200px; border:0;" 
         src="{signature_img_url}" width="200" height="200" border="0">
</td>

<td style="border:2px solid #000; padding:10px 10px 10px 24px; width:303px;">
    <span style="font-size:18pt; color:#000;">John Doe<br></span>
    <span style="font-size:10pt; line-height:16pt; color:#000;">Sales & Marketing Director, </span>
    <span style="font-size:10pt; font-weight:bold; color:#000;">My Company</span><br>
    <span style="font-size:10pt;"><strong>P:</strong> (800) 555-0199<br></span>
    <span style="font-size:10pt;"><strong>M:</strong> (800) 555-0299<br></span>
    <span style="font-size:10pt;"><strong>E:</strong>
        <a href="mailto:john.doe@my-company.com" 
           style="color:#000; text-decoration:none;">john.doe@my-company.com</a>
        <br>
    </span>
    <span style="font-size:10pt;"><strong>A:</strong> Street, City, ZIP, Country<br></span>
    <a href="http://www.my-company.com" style="text-decoration:none;">
        <strong style="color:#000; font-size:10pt;">www.my-company.com</strong>
    </a>
</td>

</tr>

<tr>
<td colspan="2" style="padding-top:11px; text-align:right;">
<a href="https://www.facebook.com/MyCompany"><img width="19" src="https://www.mail-signatures.com/signature-generator/img/templates/logo-highlight/fb.png"></a>
<a href="https://twitter.com/MyCompany404"><img width="19" src="https://www.mail-signatures.com/signature-generator/img/templates/logo-highlight/tt.png"></a>
<a href="https://www.youtube.com/user/MyCompanyChannel"><img width="19" src="https://www.mail-signatures.com/signature-generator/img/templates/logo-highlight/yt.png"></a>
<a href="https://www.linkedin.com/company/mycompany404"><img width="19" src="https://www.mail-signatures.com/signature-generator/img/templates/logo-highlight/ln.png"></a>
<a href="https://www.instagram.com/mycompany404/"><img width="19" src="https://www.mail-signatures.com/signature-generator/img/templates/logo-highlight/it.png"></a>
</td>
</tr>

</tbody>
</table>

<!-- ================= SIGNATURE END ================= -->

</body>
</html>
"""
        st.code(html, language="html")
        st.success("HTML generated successfully! Paste this in your email (HTML mode).")

# -------------------------
# Gmail Sending (optional)
# -------------------------
try:
    from auth_gmail import get_gmail_service
    gmail_service = get_gmail_service()
    gmail_ready = True
except:
    gmail_service = None
    gmail_ready = False

if gmail_ready:
    st.subheader("Send Test Email via Gmail API")

    if st.button("Send Email via Gmail"):
        if not to:
            st.error("Recipient email required!")
        else:
            try:
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText

                visible_img_url = tracking_img_url(to, message_id, visible_image or None)
                pixel_only_url = tracking_img_url(to, message_id, None)
                click_url = tracking_click_url(to, link_target, message_id)
                signature_img_url = tracking_img_url(to, message_id, signature_image or "2.jpeg")

                html = f"""
<!DOCTYPE HTML>
<html>
<body style="font-size: 10pt; font-family: Arial, sans-serif;">

<p>Hello, this is a tracked email.</p>

<img src="{visible_img_url}" width="200" height="200" alt="Image"><br><br>
<a href="{click_url}">Click this tracked link</a>
<img src="{pixel_only_url}" width="1" height="1" style="display:none;" />

<br><br>
<table cellspacing="0" cellpadding="0" border="0" 
       style="COLOR:#000; font-family:Arial; width:500px; background: transparent;">
<tbody>
<tr>

<td style="text-align:center;border: 2px solid #000; width:197px">
    <img style="width:200px; height:200px; border:0;" 
         src="{signature_img_url}" width="200" height="200" border="0">
</td>

<td style="border:2px solid #000; padding:10px 10px 10px 24px; width:303px;">
    <span style="font-size:18pt; color:#000;">John Doe<br></span>
    <span style="font-size:10pt; line-height:16pt; color:#000;">Sales & Marketing Director, </span>
    <span style="font-size:10pt; font-weight:bold; color:#000;">My Company</span><br>
    <span style="font-size:10pt;"><strong>P:</strong> (800) 555-0199<br></span>
    <span style="font-size:10pt;"><strong>M:</strong> (800) 555-0299<br></span>
    <span style="font-size:10pt;"><strong>E:</strong>
        <a href="mailto:john.doe@my-company.com" 
           style="color:#000; text-decoration:none;">john.doe@my-company.com</a><br>
    </span>
    <span style="font-size:10pt;"><strong>A:</strong> Street, City, ZIP, Country<br></span>
    <a href="http://www.my-company.com" style="text-decoration:none;">
        <strong style="color:#000; font-size:10pt;">www.my-company.com</strong>
    </a>
</td>

</tr>

<tr>
<td colspan="2" style="padding-top:11px; text-align:right;">
<a href="https://www.facebook.com/MyCompany"><img width="19" src="https://www.mail-signatures.com/signature-generator/img/templates/logo-highlight/fb.png"></a>
<a href="https://twitter.com/MyCompany404"><img width="19" src="https://www.mail-signatures.com/signature-generator/img/templates/logo-highlight/tt.png"></a>
<a href="https://www.youtube.com/user/MyCompanyChannel"><img width="19" src="https://www.mail-signatures.com/signature-generator/img/templates/logo-highlight/yt.png"></a>
<a href="https://www.linkedin.com/company/mycompany404"><img width="19" src="https://www.mail-signatures.com/signature-generator/img/templates/logo-highlight/ln.png"></a>
<a href="https://www.instagram.com/mycompany404/"><img width="19" src="https://www.mail-signatures.com/signature-generator/img/templates/logo-highlight/it.png"></a>
</td>
</tr>

</tbody>
</table>

</body>
</html>
"""

                msg = MIMEMultipart("alternative")
                msg["to"] = to
                msg["subject"] = subject
                msg.attach(MIMEText("Plain text fallback", "plain"))
                msg.attach(MIMEText(html, "html"))

                encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
                res = gmail_service.users().messages().send( # type: ignore
                    userId="me", body={"raw": encoded}
                ).execute()

                st.success("Email sent!")
                st.json(res)
            except Exception as e:
                st.error(f"Sending failed: {e}")

else:
    st.info("Gmail sending not enabled. Add auth_gmail.py to enable sending.")

# -------------------------
# Tracking Logs
# -------------------------
st.subheader("📊 Tracking Logs")
email_query = st.text_input("Search events by email")

if st.button("Fetch Email Activity"):
    try:
        res = requests.get(f"{backend_url}/tracking/by_email", params={"email": email_query}, timeout=10)
        data = res.json()

        open_count = len(data.get("opens", []))
        click_count = len(data.get("clicks", []))
        img_read_count = len(data.get("img_reads", []))

        st.markdown(f"### 📌 Summary for **{email_query}**")
        st.write(f"**Opens:** {open_count}")
        st.write(f"**Link Clicks:** {click_count}")
        st.write(f"**Image Loads:** {img_read_count}")

        df_open = pd.DataFrame(data["opens"])
        if not df_open.empty:
            df_open["time"] = pd.to_datetime(df_open["time"])
            df_open = df_open.sort_values("time", ascending=False)
        st.dataframe(df_open)

        df_img = pd.DataFrame(data["img_reads"])
        if not df_img.empty:
            df_img["time"] = pd.to_datetime(df_img["time"])
            df_img = df_img.sort_values("time", ascending=False)
        st.dataframe(df_img)

        df_click = pd.DataFrame(data["clicks"])
        if not df_click.empty:
            df_click["time"] = pd.to_datetime(df_click["time"])
            df_click = df_click.sort_values("time", ascending=False)
        st.dataframe(df_click)

    except Exception as e:
        st.error(f"Request failed: {e}")

if st.button("Refresh Latest Logs"):
    try:
        res = requests.get(f"{backend_url}/tracking/latest", timeout=10)
        data = res.json()
        st.markdown("### Latest Events")
        st.dataframe(pd.DataFrame(data["events"]))
        st.markdown("### Latest Image Reads")
        st.dataframe(pd.DataFrame(data["img_reads"]))
    except Exception as e:
        st.error(f"Failed to load logs: {e}")

st.markdown("---")
st.markdown("This dashboard works with the updated FastAPI backend and supports open, click, and image tracking.")
