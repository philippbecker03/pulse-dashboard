import random
from datetime import datetime, timedelta
from typing import List
from .models import Activity, ActivitySplit

def generate_sample_splits(distance_km: float, avg_pace_sec: int, avg_hr: int) -> List[ActivitySplit]:
    splits = []
    total_km = int(distance_km)
    for i in range(1, total_km + 1):
        # Add slight variation per km (+- 8 seconds)
        variance = random.randint(-8, 8)
        km_pace_sec = max(210, avg_pace_sec + variance)
        mins = km_pace_sec // 60
        secs = km_pace_sec % 60
        km_hr = min(195, max(110, avg_hr + random.randint(-4, 6)))
        splits.append(ActivitySplit(
            km=i,
            pace_seconds=km_pace_sec,
            pace_formatted=f"{mins}:{secs:02d}",
            avg_hr=km_hr,
            elevation_diff=round(random.uniform(-15.0, 18.0), 1)
        ))
    return splits

def generate_hr_zones_distribution(sport_type: str, intensity: str, duration_sec: int) -> dict:
    """Calculates realistic distribution of seconds spent in Z1-Z5."""
    if intensity == "recovery":
        ratios = [0.45, 0.45, 0.10, 0.0, 0.0]
    elif intensity == "endurance":
        ratios = [0.15, 0.65, 0.15, 0.05, 0.0]
    elif intensity == "tempo":
        ratios = [0.10, 0.30, 0.45, 0.15, 0.0]
    elif intensity == "intervals":
        ratios = [0.20, 0.25, 0.20, 0.20, 0.15]
    else:
        ratios = [0.20, 0.50, 0.20, 0.10, 0.0]

    return {
        "z1": int(duration_sec * ratios[0]),
        "z2": int(duration_sec * ratios[1]),
        "z3": int(duration_sec * ratios[2]),
        "z4": int(duration_sec * ratios[3]),
        "z5": int(duration_sec * ratios[4]),
    }

def get_demo_activities() -> List[Activity]:
    activities: List[Activity] = []
    now = datetime.now()
    random.seed(42)  # Deterministic seed for consistency
    
    # 60 days of training history
    run_templates = [
        {"title": "Morgenlauf im Park (Grundlage Z2)", "dist": 8.4, "pace_sec": 315, "hr": 142, "cad": 170, "elev": 45, "intensity": "endurance", "suffer": 42},
        {"title": "Lockerer Regenerationslauf", "dist": 5.2, "pace_sec": 350, "hr": 128, "cad": 166, "elev": 20, "intensity": "recovery", "suffer": 22},
        {"title": "Tempodauerlauf an der Schwellengrenze", "dist": 10.0, "pace_sec": 272, "hr": 168, "cad": 178, "elev": 60, "intensity": "tempo", "suffer": 85},
        {"title": "Intervalltraining 5x 1000m Pace 4:15", "dist": 9.5, "pace_sec": 280, "hr": 174, "cad": 182, "elev": 35, "intensity": "intervals", "suffer": 98},
        {"title": "Langer Sonntagslauf durch den Stadtwald", "dist": 18.2, "pace_sec": 330, "hr": 145, "cad": 172, "elev": 140, "intensity": "endurance", "suffer": 110},
        {"title": "Feierabendrunde mit Steigerungen", "dist": 7.8, "pace_sec": 305, "hr": 148, "cad": 174, "elev": 50, "intensity": "endurance", "suffer": 55},
        {"title": "Fahrtspiel (Fartlek) im hügeligen Gelände", "dist": 11.4, "pace_sec": 298, "hr": 162, "cad": 176, "elev": 185, "intensity": "tempo", "suffer": 88}
    ]

    ride_templates = [
        {"title": "Rennrad Grundlagen-Ausfahrt", "dist": 52.0, "speed": 28.5, "hr": 136, "cad": 88, "watts": 185, "elev": 420, "intensity": "endurance", "suffer": 75},
        {"title": "Feierabendrunde auf dem Rennrad", "dist": 34.5, "speed": 29.8, "hr": 148, "cad": 90, "watts": 210, "elev": 260, "intensity": "tempo", "suffer": 65},
        {"title": "Große Wochenend-Tour mit Höhenmetern", "dist": 78.4, "speed": 27.2, "hr": 142, "cad": 86, "watts": 195, "elev": 890, "intensity": "endurance", "suffer": 135},
        {"title": "Lockeres Kurbeln / Regeneration", "dist": 22.0, "speed": 23.5, "hr": 118, "cad": 84, "watts": 130, "elev": 95, "intensity": "recovery", "suffer": 25},
        {"title": "Gravelbike Tour über Wald- und Schotterwege", "dist": 44.0, "speed": 24.2, "hr": 150, "cad": 85, "watts": 200, "elev": 510, "intensity": "tempo", "suffer": 92}
    ]

    workout_count = 0
    # Simulate past 60 days
    for day_offset in range(60, -1, -1):
        activity_date = now - timedelta(days=day_offset, hours=random.randint(6, 18), minutes=random.randint(5, 50))
        
        # 4-5 workouts per week (skip ~2-3 days a week for rest days)
        if day_offset % 7 in [1, 5] and random.random() > 0.35:
            continue  # Rest day
            
        is_ride = (day_offset % 3 == 0) or (day_offset % 7 == 6 and random.random() > 0.4)
        
        if is_ride:
            t = random.choice(ride_templates)
            dist_km = round(t["dist"] + random.uniform(-4.0, 5.0), 1)
            speed = round(t["speed"] + random.uniform(-1.2, 1.5), 1)
            moving_sec = int((dist_km / speed) * 3600)
            elapsed_sec = moving_sec + random.randint(120, 600)
            elev = round(t["elev"] + random.uniform(-30, 50), 0)
            avg_hr = t["hr"] + random.randint(-4, 5)
            max_hr = avg_hr + random.randint(22, 35)
            watts = t["watts"] + random.randint(-15, 20)
            cad = t["cad"] + random.randint(-3, 3)
            cals = int(moving_sec * 0.22 * (watts / 180.0))
            
            # Cycling TSS
            dur_hr = moving_sec / 3600.0
            if_factor = watts / 240.0
            tss = round(100.0 * dur_hr * (if_factor ** 2), 1)
            
            act_id = f"demo-ride-{day_offset}"
            activities.append(Activity(
                id=act_id,
                source="demo",
                external_id=f"ext-{act_id}",
                title=t["title"],
                sport_type="Ride",
                start_date=activity_date,
                distance_km=dist_km,
                moving_time_seconds=moving_sec,
                elapsed_time_seconds=elapsed_sec,
                elevation_gain_m=elev,
                avg_speed_kmh=speed,
                avg_pace_min_km=None,
                avg_hr=avg_hr,
                max_hr=max_hr,
                avg_cadence=cad,
                avg_watts=float(watts),
                calories=cals,
                suffer_score=t["suffer"],
                tss=tss,
                hr_zones=generate_hr_zones_distribution("Ride", t["intensity"], moving_sec),
                splits=None,
                description=f"Automatischer Sync: {dist_km} km mit Ø {speed} km/h und {watts} Watt.",
                created_at=activity_date
            ))
        else:
            t = random.choice(run_templates)
            dist_km = round(t["dist"] + random.uniform(-0.8, 1.2), 1)
            pace_sec = t["pace_sec"] + random.randint(-6, 8)
            moving_sec = int(dist_km * pace_sec)
            elapsed_sec = moving_sec + random.randint(30, 240)
            speed = round((dist_km / (moving_sec / 3600.0)), 2)
            elev = round(t["elev"] + random.uniform(-10, 15), 0)
            avg_hr = t["hr"] + random.randint(-4, 5)
            max_hr = avg_hr + random.randint(18, 28)
            cad = t["cad"] + random.randint(-2, 2)
            cals = int(dist_km * 68)
            
            p_mins = pace_sec // 60
            p_secs = pace_sec % 60
            pace_formatted = f"{p_mins}:{p_secs:02d}"
            
            # Running TSS
            dur_hr = moving_sec / 3600.0
            if_factor = 280.0 / pace_sec
            tss = round(100.0 * dur_hr * (if_factor ** 2), 1)
            
            act_id = f"demo-run-{day_offset}"
            activities.append(Activity(
                id=act_id,
                source="demo",
                external_id=f"ext-{act_id}",
                title=t["title"],
                sport_type="Run",
                start_date=activity_date,
                distance_km=dist_km,
                moving_time_seconds=moving_sec,
                elapsed_time_seconds=elapsed_sec,
                elevation_gain_m=elev,
                avg_speed_kmh=speed,
                avg_pace_min_km=pace_formatted,
                avg_hr=avg_hr,
                max_hr=max_hr,
                avg_cadence=cad,
                avg_watts=None,
                calories=cals,
                suffer_score=t["suffer"],
                tss=tss,
                hr_zones=generate_hr_zones_distribution("Run", t["intensity"], moving_sec),
                splits=generate_sample_splits(dist_km, pace_sec, avg_hr),
                description=f"Automatischer Sync: {dist_km} km im Schnitt von {pace_formatted} min/km.",
                created_at=activity_date
            ))
            
    # Sort descending
    activities.sort(key=lambda a: a.start_date, reverse=True)
    return activities
