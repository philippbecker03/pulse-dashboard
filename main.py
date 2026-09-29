import os
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from backend.models import UserProfile, Activity, OverviewStats, TrainingSuggestion
from backend.database import (
    init_db, get_activities, get_activity_by_id, save_activity, clear_activities,
    get_user_profile, save_user_profile, get_setting, set_setting
)
from backend.sport_science import (
    compute_fitness_fatigue_timeline, get_overview_statistics,
    calculate_hr_zones, predict_race_times, estimate_vo2max
)
from backend.demo_data import get_demo_activities
from backend.strava_service import StravaService
from backend.huawei_service import HuaweiService
from backend.ai_coach import AICoachService

app = FastAPI(title="Athlete Performance Hub", version="2.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
strava_service = StravaService()
huawei_service = HuaweiService()
ai_coach_service = AICoachService()

@app.on_event("startup")
def on_startup():
    init_db()
    # Check if database has any activities. If empty, load demo activities
    existing = get_activities(limit=5)
    if not existing:
        print("Initialisiere Datenbank mit realistischen Demo-Daten...")
        demo_acts = get_demo_activities()
        for act in demo_acts:
            save_activity(act)
        set_setting("demo_mode", "true")

# API Endpoints
@app.get("/api/overview")
def get_overview():
    user = get_user_profile()
    activities = get_activities(limit=120)
    overview = get_overview_statistics(activities, user)
    return overview

@app.get("/api/trends")
def get_trends(days: int = Query(default=90, ge=14, le=365)):
    activities = get_activities(limit=250)
    timeline = compute_fitness_fatigue_timeline(activities, days=days)
    return timeline

@app.get("/api/activities")
def list_activities(
    sport: Optional[str] = "all",
    source: Optional[str] = "all",
    limit: int = 100
):
    acts = get_activities(sport_type=sport, source=source, limit=limit)
    return acts

@app.get("/api/activities/{act_id}")
def get_activity_detail(act_id: str):
    act = get_activity_by_id(act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Aktivität nicht gefunden")
    return act

@app.get("/api/zones")
def get_zones():
    user = get_user_profile()
    zones = calculate_hr_zones(user)
    return zones

@app.get("/api/profile")
def get_profile():
    return get_user_profile()

@app.post("/api/profile")
def update_profile(profile: UserProfile):
    save_user_profile(profile)
    return {"success": True, "profile": profile}

@app.get("/api/settings")
def get_settings():
    return {
        "strava_client_id": get_setting("strava_client_id", ""),
        "strava_client_secret_configured": bool(get_setting("strava_client_secret", "")),
        "strava_refresh_token_configured": bool(get_setting("strava_refresh_token", "")),
        "strava_last_sync": get_setting("strava_last_sync", ""),
        "gemini_api_key_configured": bool(get_setting("gemini_api_key", "") or os.environ.get("GEMINI_API_KEY")),
        "demo_mode": get_setting("demo_mode", "true").lower() == "true"
    }

class SettingsUpdate(BaseModel):
    strava_client_id: Optional[str] = None
    strava_client_secret: Optional[str] = None
    strava_refresh_token: Optional[str] = None
    gemini_api_key: Optional[str] = None
    demo_mode: Optional[bool] = None

@app.post("/api/settings")
def update_settings(data: SettingsUpdate):
    if data.strava_client_id is not None:
        set_setting("strava_client_id", data.strava_client_id.strip())
    if data.strava_client_secret is not None and data.strava_client_secret.strip():
        set_setting("strava_client_secret", data.strava_client_secret.strip())
    if data.strava_refresh_token is not None and data.strava_refresh_token.strip():
        set_setting("strava_refresh_token", data.strava_refresh_token.strip())
    if data.gemini_api_key is not None and data.gemini_api_key.strip():
        set_setting("gemini_api_key", data.gemini_api_key.strip())
    if data.demo_mode is not None:
        set_setting("demo_mode", "true" if data.demo_mode else "false")
    return {"success": True}

@app.get("/api/strava/auth-url")
def get_strava_auth_url():
    url = strava_service.get_oauth_url()
    if not url:
        raise HTTPException(status_code=400, detail="Bitte zuerst Strava Client ID in den Einstellungen eintragen.")
    return {"url": url}

@app.get("/api/strava/callback")
async def strava_oauth_callback(code: Optional[str] = None, error: Optional[str] = None):
    if error or not code:
        return RedirectResponse(url="/?sync=error")
    res = await strava_service.exchange_code_for_tokens(code)
    if not res.get("success"):
        return RedirectResponse(url="/?sync=token_error")
    # Trigger initial sync of activities
    await strava_service.sync_activities()
    return RedirectResponse(url="/?sync=success")

@app.post("/api/sync/strava")
async def trigger_strava_sync():
    res = await strava_service.sync_activities()
    return res

@app.get("/api/activities/{act_id}/streams")
async def get_activity_streams(act_id: str):
    """Fetches time-series streams (HR, pace, altitude, GPS) from Strava for an activity."""
    act = get_activity_by_id(act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Aktivität nicht gefunden")

    # Only supported for Strava/Huawei activities with a Strava external_id
    strava_id = act.external_id
    if not strava_id:
        return {"available": False, "reason": "Keine Strava-ID für diese Aktivität vorhanden."}

    streams = await strava_service.fetch_activity_streams(strava_id)
    if streams is None:
        return {"available": False, "reason": "Stream-Daten konnten nicht abgerufen werden (kein Strava-Token oder kein GPS aufgezeichnet)."}

    # Build clean response: extract .data arrays
    def stream_data(key: str):
        entry = streams.get(key, {})
        return entry.get("data") if entry else None

    polyline = await strava_service.fetch_activity_polyline(strava_id)

    return {
        "available": True,
        "time": stream_data("time"),
        "heartrate": stream_data("heartrate"),
        "velocity_smooth": stream_data("velocity_smooth"),  # m/s → multiply by 3.6 for km/h
        "altitude": stream_data("altitude"),
        "cadence": stream_data("cadence"),
        "latlng": stream_data("latlng"),
        "watts": stream_data("watts"),
        "polyline": polyline,
        "sport_type": act.sport_type,
        "distance_km": act.distance_km,
        "moving_time_seconds": act.moving_time_seconds,
    }

@app.get("/api/sync/huawei/info")
def get_huawei_info():
    return huawei_service.get_auto_sync_instructions()

@app.post("/api/upload")
async def upload_activity_file(file: UploadFile = File(...)):
    content = await file.read()
    act = huawei_service.parse_gpx_or_tcx(content, file.filename)
    if not act:
        raise HTTPException(status_code=400, detail="Datei konnte nicht verarbeitet werden. Bitte gültige .gpx oder .tcx Datei hochladen.")
    return {"success": True, "activity": act}

class ChatMessage(BaseModel):
    message: str

@app.post("/api/coach/chat")
async def chat_with_coach(msg: ChatMessage):
    user = get_user_profile()
    activities = get_activities(limit=30)
    advice = await ai_coach_service.generate_coach_advice(msg.message, activities, user)
    return advice

@app.post("/api/demo/clear")
def clear_demo_data():
    clear_activities(source="demo")
    set_setting("demo_mode", "false")
    return {"success": True}

# Serve frontend single page app
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(
            index_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"message": "Athlete Performance API is running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
