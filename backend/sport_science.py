import math
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
from .models import Activity, UserProfile, TrainingSuggestion, TrendDataPoint, OverviewStats

def calculate_hr_zones(user: UserProfile) -> Dict[str, Dict[str, Any]]:
    """Calculates 5 HR zones based on Max HR and Resting HR (Karvonen method)."""
    max_hr = user.max_hr
    rest_hr = user.resting_hr
    hrr = max_hr - rest_hr  # Heart Rate Reserve
    
    zones = {
        "z1": {
            "name": "Aktive Erholung",
            "desc": "Regeneration, Fettstoffwechsel",
            "min": int(rest_hr + 0.50 * hrr),
            "max": int(rest_hr + 0.60 * hrr),
            "color": "#10b981"  # Emerald
        },
        "z2": {
            "name": "Grundlagenausdauer 1",
            "desc": "Aerobe Basis, Fettverbrennung (80% des Trainings)",
            "min": int(rest_hr + 0.60 * hrr),
            "max": int(rest_hr + 0.70 * hrr),
            "color": "#06b6d4"  # Cyan
        },
        "z3": {
            "name": "Tempo / GA2",
            "desc": "Aerobe Kapazität, zügiges Tempo",
            "min": int(rest_hr + 0.70 * hrr),
            "max": int(rest_hr + 0.80 * hrr),
            "color": "#3b82f6"  # Blue
        },
        "z4": {
            "name": "Laktatschwelle",
            "desc": "Schwellenbereich, anaerob-aerob Übergang",
            "min": int(rest_hr + 0.80 * hrr),
            "max": int(rest_hr + 0.90 * hrr),
            "color": "#f59e0b"  # Amber
        },
        "z5": {
            "name": "VO2max / Maximal",
            "desc": "Spitzenbelastung, anaerobe Intervalle",
            "min": int(rest_hr + 0.90 * hrr),
            "max": max_hr,
            "color": "#ef4444"  # Red
        }
    }
    return zones

def calculate_activity_tss(act: Activity, user: UserProfile) -> float:
    """Calculates Training Stress Score (TSS) for run or ride."""
    if act.tss and act.tss > 0:
        return round(act.tss, 1)
        
    duration_hours = act.moving_time_seconds / 3600.0
    if duration_hours <= 0:
        return 0.0

    # 1. If heart rate is available, use HR-based TSS / TRIMP
    if act.avg_hr and act.avg_hr > 0 and user.max_hr > user.resting_hr:
        hrr_ratio = (act.avg_hr - user.resting_hr) / (user.max_hr - user.resting_hr)
        hrr_ratio = max(0.1, min(1.0, hrr_ratio))
        # Banister's TRIMP exponential factor
        intensity_factor = hrr_ratio * (0.64 * math.exp(1.92 * hrr_ratio))
        tss = duration_hours * intensity_factor * 100.0 * 0.7
        return round(max(5.0, min(400.0, tss)), 1)

    # 2. For running by pace
    if act.sport_type == "Run" and act.distance_km > 0:
        pace_sec_per_km = act.moving_time_seconds / act.distance_km
        threshold_pace = user.threshold_pace_sec if user.threshold_pace_sec > 0 else 280
        # Intensity factor = threshold pace / actual pace
        intensity_factor = threshold_pace / pace_sec_per_km
        tss = 100.0 * duration_hours * (intensity_factor ** 2)
        return round(max(5.0, min(350.0, tss)), 1)

    # 3. For cycling by watts or speed
    if act.sport_type == "Ride":
        if act.avg_watts and act.avg_watts > 0 and user.ftp_watts > 0:
            intensity_factor = act.avg_watts / user.ftp_watts
            tss = 100.0 * duration_hours * (intensity_factor ** 2)
            return round(max(5.0, min(450.0, tss)), 1)
        else:
            # Fallback based on speed (assuming ~25 km/h is endurance ~0.65 IF)
            speed_ratio = act.avg_speed_kmh / 28.0
            intensity_factor = max(0.4, min(1.1, speed_ratio * 0.75))
            tss = 100.0 * duration_hours * (intensity_factor ** 2)
            return round(max(5.0, min(450.0, tss)), 1)

    return round(duration_hours * 50.0, 1)

def compute_fitness_fatigue_timeline(activities: List[Activity], days: int = 90) -> List[TrendDataPoint]:
    """
    Computes rolling CTL (42d), ATL (7d), and TSB for each day over the specified period.
    Activities are aggregated per calendar day.
    """
    if not activities:
        # Generate empty timeline for last 'days' days
        today = datetime.now().date()
        return [
            TrendDataPoint(
                date=(today - timedelta(days=d)).isoformat(),
                ctl=0.0, atl=0.0, tsb=0.0, load=0.0,
                km_run=0.0, km_ride=0.0, moving_time_hours=0.0
            ) for d in range(days, -1, -1)
        ]

    # Map activities by date string YYYY-MM-DD
    daily_stats: Dict[str, Dict[str, float]] = {}
    
    # Determine date range
    today = datetime.now().date()
    start_date = today - timedelta(days=days + 45) # extra 45 days warmup for CTL smoothing
    
    cur_date = start_date
    while cur_date <= today:
        daily_stats[cur_date.isoformat()] = {
            "load": 0.0, "km_run": 0.0, "km_ride": 0.0, "time_sec": 0.0
        }
        cur_date += timedelta(days=1)
        
    for act in activities:
        d_str = act.start_date.date().isoformat()
        if d_str in daily_stats:
            daily_stats[d_str]["load"] += (act.tss or 0.0)
            daily_stats[d_str]["time_sec"] += act.moving_time_seconds
            if act.sport_type == "Run":
                daily_stats[d_str]["km_run"] += act.distance_km
            elif act.sport_type == "Ride":
                daily_stats[d_str]["km_ride"] += act.distance_km

    # Rolling calculation:
    # CTL_today = CTL_yesterday + (TSS_today - CTL_yesterday) / 42
    # ATL_today = ATL_yesterday + (TSS_today - ATL_yesterday) / 7
    ctl = 0.0
    atl = 0.0
    
    sorted_dates = sorted(daily_stats.keys())
    all_points: List[TrendDataPoint] = []
    
    for d_str in sorted_dates:
        stats = daily_stats[d_str]
        load = stats["load"]
        
        # Exponential smoothing
        ctl = ctl + (load - ctl) / 42.0
        atl = atl + (load - atl) / 7.0
        tsb = ctl - atl
        
        all_points.append(TrendDataPoint(
            date=d_str,
            ctl=round(ctl, 1),
            atl=round(atl, 1),
            tsb=round(tsb, 1),
            load=round(load, 1),
            km_run=round(stats["km_run"], 1),
            km_ride=round(stats["km_ride"], 1),
            moving_time_hours=round(stats["time_sec"] / 3600.0, 2)
        ))
        
    # Return the requested last 'days' window
    cutoff_str = (today - timedelta(days=days)).isoformat()
    return [p for p in all_points if p.date >= cutoff_str]

def estimate_vo2max(activities: List[Activity], user: UserProfile) -> float:
    """Estimates VO2max based on heart rate vs speed on recent runs."""
    run_estimates = []
    for act in activities:
        if act.sport_type == "Run" and act.distance_km >= 3.0 and act.avg_hr and act.avg_hr > 120:
            speed_m_per_min = (act.distance_km * 1000) / (act.moving_time_seconds / 60)
            hr_ratio = act.avg_hr / user.max_hr
            # Based on Firstbeat / Daniels Running Formula approximation
            if hr_ratio > 0.65:
                vo2 = (speed_m_per_min * 0.2 + (speed_m_per_min * 0.9 * 0.0) + 3.5) / hr_ratio
                if 30 <= vo2 <= 75:
                    run_estimates.append(vo2)
    
    if run_estimates:
        # Weighted towards recent runs
        return round(sum(run_estimates[-5:]) / len(run_estimates[-5:]), 1)
    return 48.5  # Solid default

def predict_race_times(activities: List[Activity]) -> Dict[str, str]:
    """Uses Pete Riegel's formula T2 = T1 * (D2 / D1)^1.06 based on best 5k/10k run."""
    best_5k_sec = None
    best_10k_sec = None
    
    for act in activities:
        if act.sport_type == "Run" and act.distance_km > 0:
            pace_sec_km = act.moving_time_seconds / act.distance_km
            if 4.5 <= act.distance_km <= 6.0:
                calc_5k = pace_sec_km * 5.0
                if best_5k_sec is None or calc_5k < best_5k_sec:
                    best_5k_sec = calc_5k
            elif act.distance_km >= 9.0:
                calc_10k = pace_sec_km * 10.0
                if best_10k_sec is None or calc_10k < best_10k_sec:
                    best_10k_sec = calc_10k

    # Fallback to realistic benchmark if no exact 5k/10k found
    if not best_5k_sec:
        best_5k_sec = 24 * 60 + 30  # 24:30 min (4:54 min/km)
    
    # Riegel predictions from 5k
    t_5k = best_5k_sec
    t_10k = t_5k * (10.0 / 5.0) ** 1.06
    t_hm = t_5k * (21.0975 / 5.0) ** 1.06
    t_m = t_5k * (42.195 / 5.0) ** 1.06
    
    def fmt_time(seconds: float) -> str:
        s = int(seconds)
        hours = s // 3600
        mins = (s % 3600) // 60
        secs = s % 60
        if hours > 0:
            return f"{hours}h {mins:02d}m {secs:02d}s"
        return f"{mins:02d}:{secs:02d} min"

    return {
        "5k": fmt_time(t_5k),
        "10k": fmt_time(t_10k),
        "hm": fmt_time(t_hm),
        "marathon": fmt_time(t_m)
    }

def generate_rule_based_training_suggestion(
    current_tsb: float,
    current_ctl: float,
    current_atl: float,
    recent_activities: List[Activity],
    user: UserProfile
) -> TrainingSuggestion:
    """Generates an intelligent training recommendation based on current TSB and fatigue."""
    from datetime import timezone
    today_str = datetime.now(timezone.utc).date().isoformat()
    
    # Determine days since last activity
    days_since_workout = 1
    last_sport = "None"
    if recent_activities:
        last_act_date = recent_activities[0].start_date
        # Normalize to naive date for simple day arithmetic
        if hasattr(last_act_date, 'tzinfo') and last_act_date.tzinfo is not None:
            last_act_date = last_act_date.astimezone().replace(tzinfo=None)
        last_date = last_act_date.date()
        days_since_workout = (datetime.now().date() - last_date).days
        last_sport = recent_activities[0].sport_type

    # Evaluate readiness by TSB
    if current_tsb < -30:
        readiness = "Erhöhte Ermüdung (Überlastungsgefahr)"
        return TrainingSuggestion(
            date=today_str,
            today_readiness=readiness,
            tsb_score=round(current_tsb, 1),
            ctl_fitness=round(current_ctl, 1),
            atl_fatigue=round(current_atl, 1),
            suggested_sport="Rest",
            title="Aktiver Ruhetag / Erholung",
            workout_type="Ruhetag & Mobilität",
            duration_min=30,
            target_distance_km=0.0,
            target_hr_range="< 115 bpm (Ruhepulsbereich)",
            target_pace_or_power="Spaziergang oder leichtes Stretching",
            description="Dein akuter Trainingsstress (ATL) liegt deutlich über deiner Langzeit-Fitness. Deine Muskeln und dein Nervensystem benötigen Superkompensation, um Leistungszuwächse abzusichern und Verletzungen vorzubeugen.",
            focus_points=[
                "Kein intensives Training heute",
                "Fokus auf 8h+ Schlaf und gesunde Proteinzufuhr",
                "15-20 Min Faszienrolle / Foam Rolling oder Spaziergang"
            ]
        )
    elif current_tsb < -15:
        readiness = "Intensive Belastungsphase (Leichte Ermüdung)"
        if last_sport == "Run":
            return TrainingSuggestion(
                date=today_str,
                today_readiness=readiness,
                tsb_score=round(current_tsb, 1),
                ctl_fitness=round(current_ctl, 1),
                atl_fatigue=round(current_atl, 1),
                suggested_sport="Ride",
                title="Gelenkschonende Grundlagenausfahrt (Z1/Z2)",
                workout_type="Aktive Regeneration auf dem Rad",
                duration_min=50,
                target_distance_km=20.0,
                target_hr_range="118 - 138 bpm (Zone 2)",
                target_pace_or_power="~140 - 170 Watt (Lockere Trittfrequenz > 85 RPM)",
                description="Gestern war ein Lauf-Tag. Um die Sehnen und Gelenke zu schonen und gleichzeitig Laktat abzubauen, empfiehlt sich heute eine flache, gleichmäßige Radausfahrt.",
                focus_points=[
                    "Hohe Trittfrequenz (85-95 RPM) für gute Durchblutung",
                    "Gleichmäßiger Puls in Zone 2, keine harten Antritte",
                    "Ausreichend Elektrolyte trinken"
                ]
            )
        else:
            return TrainingSuggestion(
                date=today_str,
                today_readiness=readiness,
                tsb_score=round(current_tsb, 1),
                ctl_fitness=round(current_ctl, 1),
                atl_fatigue=round(current_atl, 1),
                suggested_sport="Run",
                title="Lockerer Regenerationslauf (Zone 1/2)",
                workout_type="Regenerationsdauerlauf",
                duration_min=40,
                target_distance_km=6.5,
                target_hr_range="120 - 140 bpm (Zone 1 - 2)",
                target_pace_or_power="5:45 - 6:15 min/km (Sehr entspanntes Sprechtempo)",
                description="Ein lockerer Basislauf fördert die Kapillarisierung der Muskulatur ohne den Körper weiter zu ermüden.",
                focus_points=[
                    "Pace strikt diszipliniert halten (kein Tempo zum Ende)",
                    "Volle Konzentration auf saubere Fußaufsatz-Technik",
                    "Ideal auf weichem Waldboden oder Schotter"
                ]
            )
    elif current_tsb >= 5:
        readiness = "Top-Form & Voll Erholt (Peak Readiness)"
        # High readiness -> Intervals or Tempo quality session!
        return TrainingSuggestion(
            date=today_str,
            today_readiness=readiness,
            tsb_score=round(current_tsb, 1),
            ctl_fitness=round(current_ctl, 1),
            atl_fatigue=round(current_atl, 1),
            suggested_sport="Run",
            title="Qualitätstraining: Schwellenintervalle (4x 1.500m)",
            workout_type="Schwellentraining (Zone 4)",
            duration_min=55,
            target_distance_km=10.5,
            target_hr_range="165 - 178 bpm in den Intervallen",
            target_pace_or_power="4:25 - 4:35 min/km (Schwellentempo)",
            description="Deine Frische und Formkurve (TSB) sind im optimalen Wettkampf-/Qualitätsbereich! Heute ist der ideale Tag für einen wirksamen VO2max- oder Schwellenreiz.",
            focus_points=[
                "15 Min Einlaufen inkl. 3 Steigerungsläufen",
                "4x 1.500m im Schwellentempo mit je 3 Min Trabpause",
                "10 Min lockeres Auslaufen in Zone 1"
            ]
        )
    else: # -15 <= TSB <= 5 (Optimal Training Zone)
        readiness = "Gute Belastbarkeit (Optimales Aufbau-Fenster)"
        return TrainingSuggestion(
            date=today_str,
            today_readiness=readiness,
            tsb_score=round(current_tsb, 1),
            ctl_fitness=round(current_ctl, 1),
            atl_fatigue=round(current_atl, 1),
            suggested_sport="Run",
            title="Aerobischer Dauerlauf mit Fahrtspiel (Fartlek)",
            workout_type="Grundlagenausdauer Z2 mit Tempovariationen",
            duration_min=50,
            target_distance_km=8.5,
            target_hr_range="135 - 155 bpm (Zone 2 - 3)",
            target_pace_or_power="5:10 - 5:35 min/km",
            description="Dein Körper befindet sich im idealen Trainingsaufbau. Nutze den heutigen Tag für einen soliden Dauerlauf mit spielerischen Zwischenbeschleunigungen.",
            focus_points=[
                "Grundtempo stabil im aeroben Bereich halten",
                "Alle 10 Minuten 60 Sekunden knackig beschleunigen",
                "Abschließend Dehnübungen für Waden und Hüftbeuger"
            ]
        )

def get_overview_statistics(activities: List[Activity], user: UserProfile) -> OverviewStats:
    """Aggregates high-level 7-day stats, current CTL/ATL/TSB, and race estimates."""
    timeline = compute_fitness_fatigue_timeline(activities, days=90)
    current_ctl = timeline[-1].ctl if timeline else 0.0
    current_atl = timeline[-1].atl if timeline else 0.0
    current_tsb = timeline[-1].tsb if timeline else 0.0
    
    # Evaluate 7-day stats — use timezone-aware now() to match Strava UTC datetimes
    from datetime import timezone
    
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    
    total_km_run = 0.0
    total_km_ride = 0.0
    total_time_sec = 0
    total_elevation = 0.0
    
    for act in activities:
        # Normalize act.start_date to UTC-aware for safe comparison
        act_date = act.start_date
        if act_date.tzinfo is None:
            act_date = act_date.replace(tzinfo=timezone.utc)
        if act_date >= seven_days_ago:
            if act.sport_type == "Run":
                total_km_run += act.distance_km
            elif act.sport_type == "Ride":
                total_km_ride += act.distance_km
            total_time_sec += act.moving_time_seconds
            total_elevation += act.elevation_gain_m

    # TSB status badge
    if current_tsb > 20:
        tsb_status = "Formverlust / Pause"
    elif current_tsb >= 5:
        tsb_status = "Optimal erholt (Peak)"
    elif current_tsb >= -15:
        tsb_status = "Produktiver Aufbau"
    elif current_tsb >= -30:
        tsb_status = "Hohe Belastung"
    else:
        tsb_status = "Ermüdung / Ruhetag nötig"

    race_preds = predict_race_times(activities)
    vo2max = estimate_vo2max(activities, user)
    suggestion = generate_rule_based_training_suggestion(
        current_tsb, current_ctl, current_atl, activities, user
    )

    return OverviewStats(
        total_km_7d=round(total_km_run + total_km_ride, 1),
        total_km_run_7d=round(total_km_run, 1),
        total_km_ride_7d=round(total_km_ride, 1),
        total_hours_7d=round(total_time_sec / 3600.0, 1),
        total_elevation_7d=round(total_elevation, 0),
        current_ctl=current_ctl,
        current_atl=current_atl,
        current_tsb=current_tsb,
        tsb_status=tsb_status,
        estimated_vo2max=vo2max,
        predicted_5k=race_preds["5k"],
        predicted_10k=race_preds["10k"],
        predicted_hm=race_preds["hm"],
        predicted_marathon=race_preds["marathon"],
        recent_activities=activities[:10],
        today_suggestion=suggestion
    )
