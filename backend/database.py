import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from .models import Activity, UserProfile, ActivitySplit

DB_PATH = Path(__file__).resolve().parent.parent / "sports_stats.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Activities table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activities (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        external_id TEXT,
        title TEXT NOT NULL,
        sport_type TEXT NOT NULL,
        start_date TEXT NOT NULL,
        distance_km REAL NOT NULL,
        moving_time_seconds INTEGER NOT NULL,
        elapsed_time_seconds INTEGER NOT NULL,
        elevation_gain_m REAL NOT NULL,
        avg_speed_kmh REAL NOT NULL,
        avg_pace_min_km TEXT,
        avg_hr INTEGER,
        max_hr INTEGER,
        avg_cadence INTEGER,
        avg_watts REAL,
        calories INTEGER,
        suffer_score INTEGER,
        tss REAL,
        hr_zones_json TEXT,
        splits_json TEXT,
        description TEXT,
        created_at TEXT NOT NULL
    )
    """)
    
    # User Profile table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        athlete_name TEXT NOT NULL DEFAULT 'Athlet',
        max_hr INTEGER NOT NULL DEFAULT 190,
        resting_hr INTEGER NOT NULL DEFAULT 52,
        threshold_pace_sec INTEGER NOT NULL DEFAULT 280,
        ftp_watts INTEGER NOT NULL DEFAULT 240,
        weight_kg REAL NOT NULL DEFAULT 72.0,
        weekly_target_km REAL NOT NULL DEFAULT 40.0,
        primary_sport TEXT NOT NULL DEFAULT 'Multisport'
    )
    """)
    
    cursor.execute("INSERT OR IGNORE INTO user_profile (id) VALUES (1)")
    
    # Key-value Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)
    
    # Default settings
    defaults = {
        "demo_mode": "true",
        "strava_client_id": "",
        "strava_client_secret": "",
        "strava_refresh_token": "",
        "strava_access_token": "",
        "strava_expires_at": "0",
        "strava_last_sync": "",
        "gemini_api_key": ""
    }
    for k, v in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)", (k, v))
        
    conn.commit()
    conn.close()

def save_activity(act: Activity):
    conn = get_connection()
    cursor = conn.cursor()
    
    hr_zones_str = json.dumps(act.hr_zones) if act.hr_zones else None
    splits_str = json.dumps([s.model_dump() for s in act.splits]) if act.splits else None
    created_at = act.created_at.isoformat() if act.created_at else datetime.now().isoformat()
    
    cursor.execute("""
    INSERT OR REPLACE INTO activities (
        id, source, external_id, title, sport_type, start_date,
        distance_km, moving_time_seconds, elapsed_time_seconds, elevation_gain_m,
        avg_speed_kmh, avg_pace_min_km, avg_hr, max_hr, avg_cadence,
        avg_watts, calories, suffer_score, tss, hr_zones_json, splits_json,
        description, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        act.id, act.source, act.external_id, act.title, act.sport_type,
        act.start_date.isoformat(), act.distance_km, act.moving_time_seconds,
        act.elapsed_time_seconds, act.elevation_gain_m, act.avg_speed_kmh,
        act.avg_pace_min_km, act.avg_hr, act.max_hr, act.avg_cadence,
        act.avg_watts, act.calories, act.suffer_score, act.tss,
        hr_zones_str, splits_str, act.description, created_at
    ))
    conn.commit()
    conn.close()

def get_activities(sport_type: Optional[str] = None, source: Optional[str] = None, limit: int = 100) -> List[Activity]:
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM activities WHERE 1=1"
    params = []
    
    if sport_type and sport_type.lower() != "all":
        query += " AND LOWER(sport_type) = LOWER(?)"
        params.append(sport_type)
        
    if source and source.lower() != "all":
        query += " AND LOWER(source) = LOWER(?)"
        params.append(source)
        
    query += " ORDER BY datetime(start_date) DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    result = []
    for r in rows:
        hr_zones = json.loads(r["hr_zones_json"]) if r["hr_zones_json"] else None
        splits_raw = json.loads(r["splits_json"]) if r["splits_json"] else None
        splits = [ActivitySplit(**s) for s in splits_raw] if splits_raw else None
        
        result.append(Activity(
            id=r["id"],
            source=r["source"],
            external_id=r["external_id"],
            title=r["title"],
            sport_type=r["sport_type"],
            start_date=datetime.fromisoformat(r["start_date"]),
            distance_km=r["distance_km"],
            moving_time_seconds=r["moving_time_seconds"],
            elapsed_time_seconds=r["elapsed_time_seconds"],
            elevation_gain_m=r["elevation_gain_m"],
            avg_speed_kmh=r["avg_speed_kmh"],
            avg_pace_min_km=r["avg_pace_min_km"],
            avg_hr=r["avg_hr"],
            max_hr=r["max_hr"],
            avg_cadence=r["avg_cadence"],
            avg_watts=r["avg_watts"],
            calories=r["calories"],
            suffer_score=r["suffer_score"],
            tss=r["tss"],
            hr_zones=hr_zones,
            splits=splits,
            description=r["description"],
            created_at=datetime.fromisoformat(r["created_at"]) if r["created_at"] else None
        ))
    conn.close()
    return result

def get_activity_by_id(act_id: str) -> Optional[Activity]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM activities WHERE id = ?", (act_id,))
    r = cursor.fetchone()
    conn.close()
    if not r:
        return None
        
    hr_zones = json.loads(r["hr_zones_json"]) if r["hr_zones_json"] else None
    splits_raw = json.loads(r["splits_json"]) if r["splits_json"] else None
    splits = [ActivitySplit(**s) for s in splits_raw] if splits_raw else None
    
    return Activity(
        id=r["id"],
        source=r["source"],
        external_id=r["external_id"],
        title=r["title"],
        sport_type=r["sport_type"],
        start_date=datetime.fromisoformat(r["start_date"]),
        distance_km=r["distance_km"],
        moving_time_seconds=r["moving_time_seconds"],
        elapsed_time_seconds=r["elapsed_time_seconds"],
        elevation_gain_m=r["elevation_gain_m"],
        avg_speed_kmh=r["avg_speed_kmh"],
        avg_pace_min_km=r["avg_pace_min_km"],
        avg_hr=r["avg_hr"],
        max_hr=r["max_hr"],
        avg_cadence=r["avg_cadence"],
        avg_watts=r["avg_watts"],
        calories=r["calories"],
        suffer_score=r["suffer_score"],
        tss=r["tss"],
        hr_zones=hr_zones,
        splits=splits,
        description=r["description"],
        created_at=datetime.fromisoformat(r["created_at"]) if r["created_at"] else None
    )

def clear_activities(source: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    if source:
        cursor.execute("DELETE FROM activities WHERE source = ?", (source,))
    else:
        cursor.execute("DELETE FROM activities")
    conn.commit()
    conn.close()

def get_user_profile() -> UserProfile:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profile WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    if not row:
        return UserProfile()
    return UserProfile(
        athlete_name=row["athlete_name"],
        max_hr=row["max_hr"],
        resting_hr=row["resting_hr"],
        threshold_pace_sec=row["threshold_pace_sec"],
        ftp_watts=row["ftp_watts"],
        weight_kg=row["weight_kg"],
        weekly_target_km=row["weekly_target_km"],
        primary_sport=row["primary_sport"]
    )

def save_user_profile(p: UserProfile):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE user_profile SET
        athlete_name = ?,
        max_hr = ?,
        resting_hr = ?,
        threshold_pace_sec = ?,
        ftp_watts = ?,
        weight_kg = ?,
        weekly_target_km = ?,
        primary_sport = ?
    WHERE id = 1
    """, (
        p.athlete_name, p.max_hr, p.resting_hr, p.threshold_pace_sec,
        p.ftp_watts, p.weight_kg, p.weekly_target_km, p.primary_sport
    ))
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()
