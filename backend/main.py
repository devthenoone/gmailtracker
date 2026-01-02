from fastapi import FastAPI, Query, Request
from fastapi.responses import Response, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
import datetime, os, requests, urllib.parse, mimetypes
import dotenv as os # Load .env file
os.load_dotenv()
# =========================
# App
# =========================
app = FastAPI(title="Email Image Tracking Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Supabase Config
# =========================
SUPABASE_URL = os.getenv("SUPABASE_URL") # type: ignore
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") # type: ignore
BUCKET = os.getenv("SUPABASE_BUCKET", "email-images") # type: ignore

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1x1 transparent GIF
ONE_BY_ONE_GIF = bytes.fromhex(
    "47494638396101000100800000ffffff00ff21f90401000000002c000000000100010000020144003b"
)

# =========================
# Helpers
# =========================
def log_event(table: str, data: dict):
    data.setdefault("time", datetime.datetime.utcnow().isoformat())
    supabase.table(table).insert(data).execute()

def already_opened_recent(email, message_id, minutes=10):
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=minutes)

    res = (
        supabase.table("tracking_logs")
        .select("time")
        .eq("type", "pixel_open")
        .eq("email", email)
        .eq("message_id", message_id)
        .order("time", desc=True)
        .limit(1)
        .execute()
    )

    if res.data:
        t = datetime.datetime.fromisoformat(res.data[0]["time"])
        return t >= cutoff

    return False

# =========================
# IMAGE + PIXEL TRACKING
# =========================
@app.get("/api/img")
def api_img(
    email: str = Query(...),
    image: str = Query(None),
    message_id: str = None,
    request: Request = None,
):
    image_param = urllib.parse.unquote_plus(image) if image else None

    if not already_opened_recent(email, message_id):
        log_event("tracking_logs", {
            "type": "pixel_open",
            "email": email,
            "message_id": message_id,
            "image_param": image_param,
            "user_agent": request.headers.get("user-agent") if request else None,
            "remote_addr": request.client.host if request and request.client else None
        })

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Content-Disposition": "inline"
    }

    # Serve image from Supabase Storage
    if image_param and not image_param.startswith(("http://", "https://")):
        try:
            file = supabase.storage.from_(BUCKET).download(image_param)
            mime, _ = mimetypes.guess_type(image_param)
            log_event("img_reads", {
                "email": email,
                "message_id": message_id,
                "served": "storage",
                "filename": image_param
            })
            return Response(content=file, media_type=mime or "image/jpeg", headers=headers)
        except:
            pass

    # Proxy remote image
    if image_param and image_param.startswith(("http://", "https://")):
        try:
            r = requests.get(image_param, timeout=8)
            log_event("img_reads", {
                "email": email,
                "message_id": message_id,
                "served": "remote",
                "url": image_param
            })
            return Response(
                content=r.content,
                media_type=r.headers.get("Content-Type", "image/jpeg"),
                headers=headers
            )
        except:
            pass

    return Response(content=ONE_BY_ONE_GIF, media_type="image/gif", headers=headers)

# =========================
# CLICK TRACKING
# =========================
@app.get("/api/click")
def api_click(
    email: str = Query(...),
    redirect: str = Query(...),
    message_id: str = None,
    request: Request = None,
):
    log_event("tracking_logs", {
        "type": "click",
        "email": email,
        "message_id": message_id,
        "redirect": redirect,
        "user_agent": request.headers.get("user-agent"),
        "remote_addr": request.client.host if request.client else None
    })
    return RedirectResponse(url=redirect, status_code=302)

# =========================
# QUERY APIs (FOR STREAMLIT)
# =========================
@app.get("/tracking/by_email")
def tracking_by_email(email: str = Query(...)):
    opens = supabase.table("tracking_logs").select("*").eq("type", "pixel_open").eq("email", email).execute()
    clicks = supabase.table("tracking_logs").select("*").eq("type", "click").eq("email", email).execute()
    reads = supabase.table("img_reads").select("*").eq("email", email).execute()

    return {
        "opens": opens.data,
        "clicks": clicks.data,
        "img_reads": reads.data
    }

@app.get("/tracking/latest")
def tracking_latest(n: int = 200):
    events = supabase.table("tracking_logs").select("*").order("time", desc=True).limit(n).execute()
    reads = supabase.table("img_reads").select("*").order("time", desc=True).limit(n).execute()

    return {
        "events": events.data,
        "img_reads": reads.data
    }
