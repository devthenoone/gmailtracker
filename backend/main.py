from fastapi import FastAPI, Query, Request
from fastapi.responses import Response, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
from dotenv import load_dotenv
import datetime, os, requests, urllib.parse, mimetypes

# =========================
# ENV
# =========================
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
BUCKET = os.getenv("SUPABASE_BUCKET", "email-images")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# APP
# =========================
app = FastAPI(title="Email Tracking Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 1x1 Pixel
# =========================
ONE_BY_ONE_GIF = bytes.fromhex(
    "47494638396101000100800000ffffff00ff21f90401000000002c000000000100010000020144003b"
)

# =========================
# HELPERS
# =========================
def log_event(table: str, data: dict):
    data["time"] = datetime.datetime.utcnow().isoformat()
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
        return datetime.datetime.fromisoformat(res.data[0]["time"]) >= cutoff
    return False

def extract_supabase_path(url: str):
    marker = "/storage/v1/object/public/"
    if marker in url:
        return url.split(marker, 1)[1].split("/", 1)[1]
    return None

# =========================
# IMAGE / PIXEL TRACKING
# =========================
@app.get("/api/img")
def api_img(
    email: str = Query(...),
    image: str = Query(None),
    message_id: str = None,
    request: Request = None,
):
    image_param = urllib.parse.unquote_plus(image) if image else None

    # ---- log open (once per 10 mins)
    try:
        if not already_opened_recent(email, message_id):
            log_event("tracking_logs", {
                "type": "pixel_open",
                "email": email,
                "message_id": message_id,
                "image_param": image_param,
                "user_agent": request.headers.get("user-agent") if request else None,
                "remote_addr": request.client.host if request and request.client else None,
            })
    except Exception as e:
        print("OPEN LOG ERROR:", e)

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Content-Disposition": "inline"
    }

    # ---- Supabase public image
    if image_param and "supabase.co/storage/v1/object/public/" in image_param:
        try:
            path = extract_supabase_path(image_param)
            file = supabase.storage.from_(BUCKET).download(path)
            mime, _ = mimetypes.guess_type(path)

            log_event("img_reads", {
                "email": email,
                "message_id": message_id,
                "served": "storage",
                "filename": path,
                "url": image_param
            })

            return Response(file, media_type=mime or "image/jpeg", headers=headers)
        except Exception as e:
            print("SUPABASE IMAGE ERROR:", e)

    # ---- Local filename (welcome/banner.png)
    if image_param and not image_param.startswith(("http://", "https://")):
        try:
            file = supabase.storage.from_(BUCKET).download(image_param)
            mime, _ = mimetypes.guess_type(image_param)

            log_event("img_reads", {
                "email": email,
                "message_id": message_id,
                "served": "storage",
                "filename": image_param,
                "url": None
            })

            return Response(file, media_type=mime or "image/jpeg", headers=headers)
        except Exception as e:
            print("LOCAL IMAGE ERROR:", e)

    # ---- Remote image proxy
    if image_param and image_param.startswith(("http://", "https://")):
        try:
            r = requests.get(image_param, timeout=8)

            log_event("img_reads", {
                "email": email,
                "message_id": message_id,
                "served": "remote",
                "filename": None,
                "url": image_param
            })

            return Response(
                r.content,
                media_type=r.headers.get("Content-Type", "image/jpeg"),
                headers=headers
            )
        except Exception as e:
            print("REMOTE IMAGE ERROR:", e)

    # ---- fallback pixel
    return Response(ONE_BY_ONE_GIF, media_type="image/gif", headers=headers)

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
        "remote_addr": request.client.host if request and request.client else None,
    })

    return RedirectResponse(url=redirect, status_code=302)

# =========================
# DASHBOARD APIs
# =========================
@app.get("/tracking/by_email")
def tracking_by_email(email: str):
    return {
        "opens": supabase.table("tracking_logs").select("*").eq("type", "pixel_open").eq("email", email).execute().data,
        "clicks": supabase.table("tracking_logs").select("*").eq("type", "click").eq("email", email).execute().data,
        "img_reads": supabase.table("img_reads").select("*").eq("email", email).execute().data,
    }

@app.get("/tracking/latest")
def tracking_latest(n: int = 200):
    return {
        "events": supabase.table("tracking_logs").select("*").order("time", desc=True).limit(n).execute().data,
        "img_reads": supabase.table("img_reads").select("*").order("time", desc=True).limit(n).execute().data,
    }

# =========================
# ALL EMAILS DATA
# =========================
@app.get("/tracking/all")
def tracking_all():
    return {
        "events": supabase.table("tracking_logs").select("*").order("time", desc=True).execute().data,
        "opens": supabase.table("tracking_logs").select("*").eq("type", "pixel_open").execute().data,
        "clicks": supabase.table("tracking_logs").select("*").eq("type", "click").execute().data,
        "img_reads": supabase.table("img_reads").select("*").execute().data,
    }