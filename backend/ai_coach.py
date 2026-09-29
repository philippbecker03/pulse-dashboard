import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from .models import Activity, UserProfile
from .database import get_setting, get_user_profile
from .sport_science import compute_fitness_fatigue_timeline, predict_race_times, estimate_vo2max

class AICoachService:
    def __init__(self):
        pass

    def get_api_key(self) -> Optional[str]:
        # Priority: Database setting -> Environment variable
        key = get_setting("gemini_api_key", "").strip()
        if not key:
            key = os.environ.get("GEMINI_API_KEY", "").strip()
        return key if key else None

    async def generate_coach_advice(
        self,
        user_message: str,
        activities: List[Activity],
        user: UserProfile
    ) -> Dict[str, Any]:
        """
        Generates context-aware coaching advice using Gemini 3.8 Flash,
        or sport-science logic if no key is present.
        """
        api_key = self.get_api_key()
        
        # Calculate current physiological parameters
        timeline = compute_fitness_fatigue_timeline(activities, days=30)
        current_ctl = timeline[-1].ctl if timeline else 0.0
        current_atl = timeline[-1].atl if timeline else 0.0
        current_tsb = timeline[-1].tsb if timeline else 0.0
        vo2max = estimate_vo2max(activities, user)
        races = predict_race_times(activities)

        # Context summary
        recent_summary = []
        for act in activities[:5]:
            recent_summary.append(
                f"- {act.start_date.strftime('%d.%m.%Y')}: {act.sport_type} '{act.title}' ({act.distance_km} km in {act.moving_time_seconds//60} Min, Ø HR: {act.avg_hr or 'k.A.'} bpm, Pace/Speed: {act.avg_pace_min_km or str(act.avg_speed_kmh)+' km/h'})"
            )
        recent_str = "\n".join(recent_summary) if recent_summary else "Keine aktuellen Aktivitäten vorhanden."

        system_context = f"""
Du bist ein erfahrener, evidenzbasierter Ausdauertrainer und Sportwissenschaftler (Coach für Laufen und Radsport).
Du analysierst die Trainingsdaten des Athleten basierend auf dem Banister/Coggan-Modell (Fitness CTL, Ermüdung ATL, Form TSB) und der 80/20 Polarisierungs-Methode (80% Zone 2 Grundlagenausdauer, 20% hochintensive Qualität).

Athleten-Profil:
- Name: {user.athlete_name}
- Max. Herzfrequenz: {user.max_hr} bpm | Ruhepuls: {user.resting_hr} bpm
- Schwellenpace (Laufen): {user.threshold_pace_sec//60}:{user.threshold_pace_sec%60:02d} min/km
- FTP (Radsport): {user.ftp_watts} Watt
- Wöchentliches Kilometer-Ziel: {user.weekly_target_km} km

Aktueller physiologischer Zustand:
- Fitness (CTL - Langzeitform): {current_ctl}
- Ermüdung (ATL - Akuter Stress 7d): {current_atl}
- Form (TSB = CTL - ATL): {current_tsb}
  (Bedeutung: > +5 frisch/optimal, -10 bis -30 optimaler Aufbau, < -30 Überlastungsgefahr!)
- Geschätzte VO2max: {vo2max} ml/kg/min
- Prognostizierte Wettkampfzeiten: 5k: {races['5k']}, 10k: {races['10k']}, Halbmarathon: {races['hm']}, Marathon: {races['marathon']}

Letzte Einheiten:
{recent_str}

Instruktionen für deine Antwort:
1. Antworte auf Deutsch, motivierend, professionell und präzise.
2. Beziehe dich explizit auf den aktuellen TSB-Wert ({current_tsb}) und die letzten Einheiten.
3. Gib konkrete, umsetzbare Empfehlungen mit exakten Herzfrequenz- oder Pace-Bereichen.
4. Strukturiere deine Antwort übersichtlich mit Absätzen und Aufzählungspunkten.
"""

        # If Gemini API key is available, use google-genai
        if api_key:
            from google import genai
            client = genai.Client(api_key=api_key)
            full_prompt = f"{system_context}\n\nFrage / Anliegen des Athleten:\n\"{user_message}\""
            
            models_to_try = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-flash-latest"]
            last_err = None
            
            for m in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=m,
                        contents=full_prompt
                    )
                    if response and response.text:
                        return {
                            "provider": m,
                            "response": response.text,
                            "timestamp": datetime.now().strftime("%H:%M"),
                            "tsb": current_tsb,
                            "ctl": current_ctl,
                            "notice": f"Beantwortet mit {m} (Gemini AI)"
                        }
                except Exception as e:
                    last_err = str(e)
                    print(f"Gemini model {m} failed: {e}")
                    continue

        # Local algorithmic fallback coach
        notice_text = "Tipp: Für unbegrenzte freie KI-Konversationen kannst du in den Einstellungen deinen Gemini API-Key hinterlegen."
        if api_key and last_err:
            notice_text = f"Hinweis: Google Gemini meldet temporäre Auslastung. Die sportwissenschaftliche Engine hat diese Antwort generiert."

        return {
            "provider": "sport-science-engine",
            "response": self._generate_local_advice(user_message, current_tsb, current_ctl, current_atl, activities, user),
            "timestamp": datetime.now().strftime("%H:%M"),
            "tsb": current_tsb,
            "ctl": current_ctl,
            "notice": notice_text
        }

    def _generate_local_advice(
        self,
        query: str,
        tsb: float,
        ctl: float,
        atl: float,
        activities: List[Activity],
        user: UserProfile
    ) -> str:
        q_lower = query.lower()
        
        # Scenario 1: Training for today / next session
        if any(w in q_lower for w in ["heute", "morgen", "nächste", "training", "plan", "was soll ich"]):
            if tsb < -25:
                return (
                    f"### 🛑 Fokus heute: Regeneration & Entlastung (TSB: {tsb})\n\n"
                    f"Deine akute Ermüdung (ATL: {atl}) übersteigt deine Fitness (CTL: {ctl}) spürbar. "
                    f"Ein intensives Training würde heute das Verletzungsrisiko erhöhen und die Anpassung dämpfen.\n\n"
                    f"**Empfehlung für heute:**\n"
                    f"- **Option A:** Kompletter Ruhetag, 20 Minuten Mobility & Dehnen.\n"
                    f"- **Option B:** Sehr lockere Radausfahrt (max. 45 Min) in Zone 1 (< 120 bpm) mit hoher Trittfrequenz (> 90 RPM), um den Laktatabtransport zu beschleunigen."
                )
            elif tsb >= 5:
                return (
                    f"### ⚡ Fokus heute: Höchste Leistungsbereitschaft (TSB: +{tsb})\n\n"
                    f"Dein Körper ist bestens erholt und deine Formkurve ist im Peak-Fenster! "
                    f"Nutze diesen Frischezustand für einen anspruchsvollen Trainingsreiz.\n\n"
                    f"**Empfohlenes Workout: Schwellen-Intervalle (Laufen)**\n"
                    f"- **Einlaufen:** 15 Min locker in Zone 2 + 3x 80m Steigerungsläufe.\n"
                    f"- **Kernteil:** 4x 1.500m im Schwellentempo (~{user.threshold_pace_sec//60}:{user.threshold_pace_sec%60:02d} min/km) mit je 3 Min Trabpause.\n"
                    f"- **Auslaufen:** 10 Min ruhiges Auslaufen in Zone 1 (< 130 bpm)."
                )
            else:
                return (
                    f"### 🏃 Fokus heute: Aerobe Basis & Grundlagenausdauer (TSB: {tsb})\n\n"
                    f"Du befindest dich im optimalen physiologischen Aufbau-Bereich. Wir setzen heute auf das 80/20 Prinzip.\n\n"
                    f"**Empfohlenes Workout: 50 Min Zone-2 Dauerlauf**\n"
                    f"- **Dauer:** 50 - 60 Minuten\n"
                    f"- **Herzfrequenz:** Streng in Zone 2 ({int(user.resting_hr + 0.6*(user.max_hr-user.resting_hr))} - {int(user.resting_hr + 0.7*(user.max_hr-user.resting_hr))} bpm)\n"
                    f"- **Fokus:** Ruhige Nasenatmung, gleichmäßige Schrittfrequenz (~170 Schritte/Min)."
                )

        # Scenario 2: Questions about form, fatigue, stats
        if any(w in q_lower for w in ["form", "ermüdung", "zustand", "tsb", "ctl", "fitness"]):
            return (
                f"### 📊 Deine physiologische Form-Analyse:\n\n"
                f"- **Fitness (CTL): {ctl}** – Repräsentiert deine über 6 Wochen aufgebaute Ausdauerbasis.\n"
                f"- **Ermüdung (ATL): {atl}** – Repräsentiert den Trainingsstress der vergangenen 7 Tage.\n"
                f"- **Formkurve (TSB): {tsb}**\n\n"
                f"**Einordnung:** "
                + ("Du bist im grünen Bereich für den optimalen Formaufbau." if -20 <= tsb <= 5 else "Achte auf gezielte Erholungsphasen, um ein Plateau zu vermeiden.")
            )

        # Default general coach response
        return (
            f"Hallo {user.athlete_name}! Dein aktueller Trainingszustand liegt bei einem TSB-Wert von **{tsb}** (Fitness: {ctl}, Ermüdung: {atl}).\n\n"
            f"Für eine optimale Leistungsentwicklung bei Laufen und Radfahren empfehlen wir:\n"
            f"1. **80% lockeres Training** in Zone 2 (unterhält die aerobe Mitochondrienbildung).\n"
            f"2. **20% gezielte Qualität** (Schwellenläufe oder K3-Kraftausdauer am Berg).\n"
            f"3. **Mindestens 1-2 echte Ruhetage** pro Woche zur Superkompensation.\n\n"
            f"Du kannst mich jederzeit fragen: *'Was soll ich heute trainieren?'*, *'Wie bereite ich mich auf einen Halbmarathon vor?'* oder *'Wie ist meine aktuelle Form?'*."
        )
