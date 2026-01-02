# main.py
from fastapi import FastAPI, Query, Request
from fastapi.responses import Response, RedirectResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import datetime, json, os, requests, urllib.parse, mimetypes

app = FastAPI(title="Email Image Tracking Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Persistent Storage
# =========================
BASE_DIR = os.getenv("DATA_DIR", "/data")
LOG_FILE = f"{BASE_DIR}/tracking_logs.jsonl"
IMG_READ_FILE = f"{BASE_DIR}/img_reads.jsonl"
UPLOAD_FOLDER = f"{BASE_DIR}/uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 1x1 transparent GIF
ONE_BY_ONE_GIF = bytes.fromhex(
    "47494638396101000100800000ffffff00ff21f90401000000002c000000000100010000020144003b"
)

# =========================
# Helpers
# =========================
def ensure_file(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        open(path, "w", encoding="utf-8").close()

def append_event(path: str, obj: dict):
    obj.setdefault("time", datetime.datetime.utcnow().isoformat() + "Z")
    ensure_file(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def read_jsonl(path: str):
    ensure_file(path)
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except:
                pass
    return out

def already_opened_recent(email, message_id, minutes=10):
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=minutes)
    for e in reversed(read_jsonl(LOG_FILE)):
        if e.get("type") == "pixel_open" and e.get("email") == email:
            if e.get("message_id") == message_id:
                try:
                    t = datetime.datetime.fromisoformat(e["time"].replace("Z", ""))
                    if t >= cutoff:
                        return True
                except:
                    pass
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
        append_event(LOG_FILE, {
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

    # Serve local image
    if image_param and not image_param.startswith(("http://", "https://")):
        fpath = os.path.join(UPLOAD_FOLDER, os.path.basename(image_param))
        if os.path.exists(fpath):
            mime, _ = mimetypes.guess_type(fpath)
            mime = mime or "application/octet-stream"
            with open(fpath, "rb") as f:
                content = f.read()
            append_event(IMG_READ_FILE, {
                "email": email,
                "message_id": message_id,
                "served": "local",
                "filename": image_param
            })
            return Response(content=content, media_type=mime, headers=headers)

    # Proxy remote image
    if image_param and image_param.startswith(("http://", "https://")):
        try:
            r = requests.get(image_param, timeout=8)
            append_event(IMG_READ_FILE, {
                "email": email,
                "message_id": message_id,
                "served": "remote",
                "url": image_param
            })
            return Response(content=r.content,
                            media_type=r.headers.get("Content-Type", "image/jpeg"),
                            headers=headers)
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
    append_event(LOG_FILE, {
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
    logs = read_jsonl(LOG_FILE)
    reads = read_jsonl(IMG_READ_FILE)
    return {
        "opens": [x for x in logs if x.get("type") == "pixel_open" and x.get("email") == email],
        "clicks": [x for x in logs if x.get("type") == "click" and x.get("email") == email],
        "img_reads": [x for x in reads if x.get("email") == email],
    }

@app.get("/tracking/latest")
def tracking_latest(n: int = 200):
    return {
        "events": list(reversed(read_jsonl(LOG_FILE)))[:n],
        "img_reads": list(reversed(read_jsonl(IMG_READ_FILE)))[:n],
    }

@app.get("/tracking/download")
def download_logs():
    return FileResponse(LOG_FILE, filename="tracking_logs.jsonl")

@app.get("/tracking/download_imgreads")
def download_imgreads():
    return FileResponse(IMG_READ_FILE, filename="img_reads.jsonl")
