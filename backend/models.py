from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ActivitySplit(BaseModel):
    km: int
    pace_seconds: int
    pace_formatted: str
    avg_hr: Optional[int] = None
    elevation_diff: Optional[float] = None

class Activity(BaseModel):
    id: str
    source: str = "strava"  # "strava", "huawei", "demo", "manual"
    external_id: Optional[str] = None
    title: str
    sport_type: str  # "Run" or "Ride"
    start_date: datetime
    distance_km: float
    moving_time_seconds: int
    elapsed_time_seconds: int
    elevation_gain_m: float
    avg_speed_kmh: float
    avg_pace_min_km: Optional[str] = None
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    avg_cadence: Optional[int] = None
    avg_watts: Optional[float] = None
    calories: Optional[int] = None
    suffer_score: Optional[int] = None
    tss: Optional[float] = None  # Training Stress Score
    hr_zones: Optional[Dict[str, int]] = None  # e.g. {"z1": 600, "z2": 1800, ...} seconds in zones
    splits: Optional[List[ActivitySplit]] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None

class UserProfile(BaseModel):
    athlete_name: str = "Athlet"
    max_hr: int = 190
    resting_hr: int = 52
    threshold_pace_sec: int = 280  # 4:40 min/km in seconds
    ftp_watts: int = 240           # Functional Threshold Power for cycling
    weight_kg: float = 72.0
    weekly_target_km: float = 40.0
    primary_sport: str = "Multisport"  # "Run", "Ride", "Multisport"

class StravaSettings(BaseModel):
    client_id: Optional[str] = ""
    client_secret: Optional[str] = ""
    refresh_token: Optional[str] = ""
    access_token: Optional[str] = ""
    expires_at: Optional[int] = 0
    auto_sync: bool = True
    last_sync: Optional[datetime] = None

class AppSettings(BaseModel):
    gemini_api_key: Optional[str] = ""
    demo_mode: bool = True
    theme: str = "dark"

class TrainingSuggestion(BaseModel):
    date: str
    today_readiness: str  # "Optimal", "Gut erholt", "Aufbauphase", "Erhöhte Ermüdung", "Ruhetag dringend empfohlen"
    tsb_score: float
    ctl_fitness: float
    atl_fatigue: float
    suggested_sport: str  # "Run", "Ride", "Rest", "Alternative"
    title: str
    workout_type: str  # "Regeneration (Z1)", "Grundlage (Z2)", "Tempo (Z3)", "Schwellentraining (Z4)", "VO2max Intervalle (Z5)", "Ruhetag"
    duration_min: int
    target_distance_km: Optional[float] = None
    target_hr_range: str
    target_pace_or_power: str
    description: str
    focus_points: List[str]

class TrendDataPoint(BaseModel):
    date: str
    ctl: float  # Fitness
    atl: float  # Fatigue
    tsb: float  # Form
    load: float # Daily TSS
    km_run: float
    km_ride: float
    moving_time_hours: float

class OverviewStats(BaseModel):
    total_km_7d: float
    total_km_run_7d: float
    total_km_ride_7d: float
    total_hours_7d: float
    total_elevation_7d: float
    current_ctl: float
    current_atl: float
    current_tsb: float
    tsb_status: str
    estimated_vo2max: float
    predicted_5k: str
    predicted_10k: str
    predicted_hm: str
    predicted_marathon: str
    recent_activities: List[Activity]
    today_suggestion: TrainingSuggestion
