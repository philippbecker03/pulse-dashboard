import time
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional
from .models import Activity, ActivitySplit, UserProfile
from .database import get_setting, set_setting, save_activity, get_user_profile
from .sport_science import calculate_activity_tss

STRAVA_API_BASE = "https://www.strava.com/api/v3"
STRAVA_OAUTH_TOKEN_URL = "https://www.strava.com/oauth/token"

class StravaService:
    def __init__(self):
        pass

    def get_oauth_url(self, redirect_uri: str = "http://localhost:8000/api/strava/callback") -> Optional[str]:
        creds = self.get_credentials()
        client_id = creds["client_id"]
        if not client_id:
            return None
        return (
            f"https://www.strava.com/oauth/authorize?client_id={client_id}"
            f"&response_type=code&redirect_uri={redirect_uri}"
            f"&approval_prompt=auto&scope=read,activity:read_all"
        )

    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        creds = self.get_credentials()
        client_id = creds["client_id"]
        client_secret = creds["client_secret"]
        if not client_id or not client_secret:
            return {"success": False, "error": "Client ID oder Client Secret fehlt."}

        async with httpx.AsyncClient() as client:
            resp = await client.post(STRAVA_OAUTH_TOKEN_URL, data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code"
            })
            if resp.status_code == 200:
                data = resp.json()
                set_setting("strava_access_token", data.get("access_token", ""))
                set_setting("strava_refresh_token", data.get("refresh_token", ""))
                set_setting("strava_expires_at", str(data.get("expires_at", 0)))
                # Update athlete name if present
                athlete = data.get("athlete", {})
                if athlete:
                    first = athlete.get("firstname", "")
                    last = athlete.get("lastname", "")
                    name = f"{first} {last}".strip()
                    if name:
                        u = get_user_profile()
                        u.athlete_name = name
                        save_user_profile(u)
                return {"success": True}
            else:
                return {"success": False, "error": f"Strava Fehler: {resp.status_code} - {resp.text}"}

    def get_credentials(self) -> Dict[str, str]:
        return {
            "client_id": get_setting("strava_client_id", ""),
            "client_secret": get_setting("strava_client_secret", ""),
            "refresh_token": get_setting("strava_refresh_token", ""),
            "access_token": get_setting("strava_access_token", ""),
            "expires_at": get_setting("strava_expires_at", "0"),
            "last_sync": get_setting("strava_last_sync", "")
        }

    async def get_valid_access_token(self) -> Optional[str]:
        creds = self.get_credentials()
        client_id = creds["client_id"]
        client_secret = creds["client_secret"]
        refresh_token = creds["refresh_token"]
        access_token = creds["access_token"]
        expires_at = int(creds["expires_at"] or "0")

        if not refresh_token or not client_id or not client_secret:
            return None

        # Check if current access token is valid for at least 2 minutes
        if access_token and time.time() < (expires_at - 120):
            return access_token

        # Refresh token needed
        async with httpx.AsyncClient() as client:
            resp = await client.post(STRAVA_OAUTH_TOKEN_URL, data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            })
            if resp.status_code == 200:
                data = resp.json()
                new_token = data.get("access_token")
                new_refresh = data.get("refresh_token", refresh_token)
                new_expires = str(data.get("expires_at", 0))

                set_setting("strava_access_token", new_token)
                set_setting("strava_refresh_token", new_refresh)
                set_setting("strava_expires_at", new_expires)
                return new_token
            else:
                return None

    async def sync_activities(self, max_activities: int = 50) -> Dict[str, Any]:
        token = await self.get_valid_access_token()
        if not token:
            return {
                "success": False,
                "error": "Keine gültigen Strava-Zugangsdaten konfiguriert. Bitte trage deine Strava Client ID, Client Secret und Refresh Token in den Einstellungen ein."
            }

        user = get_user_profile()
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{STRAVA_API_BASE}/athlete/activities",
                headers=headers,
                params={"per_page": min(100, max_activities), "page": 1}
            )
            
            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"Strava API Fehler: {resp.status_code} - {resp.text}"
                }

            strava_items = resp.json()
            synced_count = 0
            huawei_count = 0

            for item in strava_items:
                sport_raw = item.get("type", "")
                if sport_raw in ["Run", "TrailRun", "VirtualRun"]:
                    sport_type = "Run"
                elif sport_raw in ["Ride", "VirtualRide", "GravelRide", "MountainBikeRide", "EBikeRide"]:
                    sport_type = "Ride"
                else:
                    continue  # We focus primarily on Run and Ride

                # Detect if workout originated from Huawei Health / Health Sync
                device_name = str(item.get("device_name", "")).lower()
                desc = str(item.get("description", "")).lower()
                ext_id = str(item.get("external_id", "")).lower()
                
                is_huawei = ("huawei" in device_name or "huawei" in desc or "huawei" in ext_id or
                             "health sync" in desc or "healthsync" in ext_id)
                source = "huawei" if is_huawei else "strava"
                if is_huawei:
                    huawei_count += 1

                # Distance in km
                dist_km = round(item.get("distance", 0.0) / 1000.0, 2)
                moving_sec = item.get("moving_time", 0)
                elapsed_sec = item.get("elapsed_time", moving_sec)
                elev = round(item.get("total_elevation_gain", 0.0), 1)

                # Speeds & Pace
                speed_mps = item.get("average_speed", 0.0)
                speed_kmh = round(speed_mps * 3.6, 2)
                
                pace_str = None
                if sport_type == "Run" and dist_km > 0 and moving_sec > 0:
                    pace_sec_km = moving_sec / dist_km
                    mins = int(pace_sec_km // 60)
                    secs = int(pace_sec_km % 60)
                    pace_str = f"{mins}:{secs:02d}"

                avg_hr = int(item.get("average_heartrate")) if item.get("average_heartrate") else None
                max_hr = int(item.get("max_heartrate")) if item.get("max_heartrate") else None
                cadence = int(item.get("average_cadence")) if item.get("average_cadence") else None
                watts = float(item.get("average_watts")) if item.get("average_watts") else None
                calories = int(item.get("kilojoules", 0) * 0.239) if item.get("kilojoules") else None
                suffer = item.get("suffer_score")

                # Parse date
                dt_str = item.get("start_date", "").replace("Z", "+00:00")
                start_date = datetime.fromisoformat(dt_str)

                # Create Activity model
                act = Activity(
                    id=f"strava-{item.get('id')}",
                    source=source,
                    external_id=str(item.get("id")),
                    title=item.get("name", "Sport-Aktivität"),
                    sport_type=sport_type,
                    start_date=start_date,
                    distance_km=dist_km,
                    moving_time_seconds=moving_sec,
                    elapsed_time_seconds=elapsed_sec,
                    elevation_gain_m=elev,
                    avg_speed_kmh=speed_kmh,
                    avg_pace_min_km=pace_str,
                    avg_hr=avg_hr,
                    max_hr=max_hr,
                    avg_cadence=cadence,
                    avg_watts=watts,
                    calories=calories,
                    suffer_score=suffer,
                    tss=None,
                    description=item.get("description"),
                    created_at=datetime.now()
                )
                
                # Calculate TSS
                act.tss = calculate_activity_tss(act, user)
                save_activity(act)
                synced_count += 1

            now_iso = datetime.now().strftime("%d.%m.%Y %H:%M")
            set_setting("strava_last_sync", now_iso)
            set_setting("demo_mode", "false")

            return {
                "success": True,
                "synced_count": synced_count,
                "huawei_detected": huawei_count,
                "last_sync": now_iso
            }

    async def fetch_activity_streams(self, strava_id: str) -> Optional[Dict[str, Any]]:
        """Fetches time-series data streams from Strava API for a given activity ID."""
        token = await self.get_valid_access_token()
        if not token:
            return None

        stream_keys = "time,heartrate,velocity_smooth,altitude,cadence,latlng,watts"
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{STRAVA_API_BASE}/activities/{strava_id}/streams",
                headers=headers,
                params={"keys": stream_keys, "key_by_type": "true"}
            )
            if resp.status_code == 200:
                return resp.json()
            return None

    async def fetch_activity_polyline(self, strava_id: str) -> Optional[str]:
        """Fetches the encoded polyline of an activity from Strava API."""
        token = await self.get_valid_access_token()
        if not token:
            return None

        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{STRAVA_API_BASE}/activities/{strava_id}",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                # Try summary first, then detailed polyline
                poly = data.get("map", {}).get("polyline") or data.get("map", {}).get("summary_polyline")
                return poly
            return None

