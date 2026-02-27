"""
gemini_service.py — Production Gemini 1.5 Flash AI service for KDMS.
All 4 jobs: risk scoring, 72hr prediction, SMS generation, national SitRep.
"""
import os
import json
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()

_model = None
_executor = ThreadPoolExecutor(max_workers=4)


def _init_model():
    global _model
    if _model is None and GEMINI_KEY:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_KEY)
        _model = genai.GenerativeModel(
            "gemini-1.5-flash",
            generation_config={"temperature": 0.3, "max_output_tokens": 1024},
        )
    return _model


def _extract_json(text: str):
    """Strip markdown fences and parse JSON."""
    text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    # Handle trailing commas
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


async def _generate(prompt: str) -> str:
    """Run Gemini generation in a thread pool (it's synchronous SDK)."""
    model = _init_model()
    if not model:
        raise RuntimeError("Gemini API key not configured")
    loop = asyncio.get_event_loop()
    resp = await loop.run_in_executor(_executor, model.generate_content, prompt)
    return resp.text


# ── Job 1: County Risk Scoring ───────────────────────────────────────────────

async def score_county_risk(county: str, weather: dict) -> dict:
    """
    Analyse weather data and output a structured risk score for a county.
    Returns: {risk_score, disaster_type, confidence, reasoning}
    """
    try:
        prompt = f"""You are a disaster risk analyst for Kenya's National Disaster Management Authority (NDMA).

Analyse the following real-time weather data for **{county}** county and provide a precise risk assessment.

Weather Data:
{json.dumps(weather, indent=2)}

Context for Kenya risk assessment:
- Rainfall > 30mm/hr = extreme flood risk in low-lying counties (Tana River, Garissa, Budalang'i)
- Temperature > 38°C + humidity < 20% = wildfire risk (Turkana, Marsabit, Samburu)
- Strong winds > 20km/h in highland counties = landslide risk if combined with rain
- Consecutive dry days in northern counties = drought escalation

Respond with ONLY valid JSON (no markdown, no explanation):
{{
  "risk_score": <integer 0-100>,
  "disaster_type": "<Flood|Drought|Wildfire|Earthquake|Landslide|None>",
  "confidence": "<High|Medium|Low>",
  "reasoning": "<one precise sentence citing specific data values>"
}}"""
        text = await _generate(prompt)
        result = _extract_json(text)
        result["risk_score"] = max(0, min(100, int(result.get("risk_score", 0))))
        return result
    except Exception as e:
        print(f"[Gemini] Risk scoring fallback for {county}: {e}")
        return _fallback_risk(county, weather)


def _fallback_risk(county: str, weather: dict) -> dict:
    import random
    rainfall = weather.get("rainfall_mm", 0)
    temp = weather.get("temp_c", 25)
    score = min(100, int(rainfall * 2.5 + max(0, temp - 32) * 1.5 + random.randint(0, 15)))
    dtype = "Flood" if rainfall > 20 else "Drought" if temp > 36 and rainfall < 2 else "None"
    return {
        "risk_score":    score,
        "disaster_type": dtype,
        "confidence":    "Low",
        "reasoning":     f"Auto-calculated from rainfall={rainfall:.1f}mm, temp={temp:.1f}°C (Gemini unavailable).",
    }


# ── Job 2: 72hr Predictive Warning ───────────────────────────────────────────

async def generate_72hr_prediction(county_forecasts: list[dict]) -> list[dict]:
    """
    Analyse 7-day forecasts and return counties at risk within 72 hours.
    Returns: [{county, threat, probability, estimated_time, recommended_action}]
    """
    try:
        # Summarise forecasts to fit context window
        summaries = []
        for fc in county_forecasts[:20]:
            daily = fc.get("forecast", {})
            precip = daily.get("precipitation_sum", [])
            temp_max = daily.get("temperature_2m_max", [])
            summaries.append({
                "county": fc["county"],
                "region": fc.get("region"),
                "next_3day_rainfall_mm": sum(precip[:3]) if precip else None,
                "max_temp_3day": max(temp_max[:3]) if temp_max else None,
            })

        prompt = f"""You are the AI prediction engine for Kenya's NDMA Early Warning System.

Analyse the 72-hour weather outlook for Kenya counties below and identify credible disaster threats.
Only flag counties where threat probability is Medium or higher based on the data.

Forecast summaries (next 3 days):
{json.dumps(summaries, indent=2)}

Risk thresholds:
- Flood: >50mm cumulative rainfall in 3 days → High risk; >25mm → Medium risk
- Drought: <5mm over 3 days AND max_temp > 35°C in arid north → Medium+
- Landslide: >40mm in highland county (Elgeyo-Marakwet, Kericho, Nyeri, Murang'a) → High

Respond with ONLY a valid JSON array (no markdown):
[
  {{
    "county": "<county name>",
    "threat": "<Flood|Drought|Wildfire|Landslide|Storm>",
    "probability": "<High|Medium|Low>",
    "estimated_time": "<within 24hrs|within 48hrs|within 72hrs>",
    "recommended_action": "<specific NDMA pre-emptive action, 10-15 words>"
  }}
]
Return [] if no credible threats found."""
        text = await _generate(prompt)
        return _extract_json(text)
    except Exception as e:
        print(f"[Gemini] 72hr prediction fallback: {e}")
        return []


# ── Job 3: SMS Alert Generation ───────────────────────────────────────────────

async def generate_sms_alert(disaster: dict, refuges: list[dict]) -> dict:
    """
    Generate bilingual SMS alert (English + Swahili), strictly under 160 chars each.
    Returns: {english, swahili}
    """
    try:
        refuge_names = ", ".join(r["name"] for r in refuges[:2]) if refuges else "nearest county offices"
        prompt = f"""You are the Kenya NDMA emergency communications system.

Write two SMS alerts for a disaster event — one English, one Swahili.
STRICT REQUIREMENT: Each message must be under 160 characters including spaces.
Include: alert keyword, disaster type, affected area, refuge location, emergency number.

Disaster:
- Type: {disaster.get('type')}
- Location: {disaster.get('county_name') or disaster.get('location')} County
- Severity: {disaster.get('severity')}
- People at risk: {disaster.get('affected_people', 0):,}
- Nearest refuge: {refuge_names}
- Emergency line: 1199

Respond with ONLY valid JSON (no markdown):
{{"english": "<message under 160 chars>", "swahili": "<message under 160 chars>"}}"""
        text = await _generate(prompt)
        result = _extract_json(text)
        # Enforce 160-char hard cap
        for lang in ("english", "swahili"):
            if len(result.get(lang, "")) > 160:
                result[lang] = result[lang][:157] + "..."
        return result
    except Exception as e:
        print(f"[Gemini] SMS alert fallback: {e}")
        return _fallback_sms(disaster)


def _fallback_sms(disaster: dict) -> dict:
    county = disaster.get("county_name") or disaster.get("location", "your area")
    dtype  = disaster.get("type", "disaster")
    return {
        "english": f"NDMA ALERT: {dtype} warning in {county}. Evacuate to nearest refuge immediately. Call 1199.",
        "swahili": f"TAHADHARI: {dtype} katika {county}. Nenda kituo cha wakimbizi. Piga simu 1199.",
    }


# ── Job 4: National Situation Report ─────────────────────────────────────────

async def generate_national_report(disasters: list[dict], stats: dict) -> str:
    """
    Generate a professional NDMA national situation report in markdown.
    Returns: formatted markdown string.
    """
    try:
        active = [d for d in disasters if d.get("status") == "active"]
        prompt = f"""You are the NDMA Kenya National Operations Centre AI system.
Generate a formal Situation Report (SitRep) for senior NDMA officers and Cabinet Secretary.

Date: {__import__('datetime').datetime.utcnow().strftime('%d %B %Y, %H:%M UTC')}

Current National Status:
- Active disaster incidents: {stats.get('active_disasters')}
- Total estimated affected population: {stats.get('total_affected', 0):,}
- Counties at elevated risk (score ≥70): {stats.get('high_risk_counties')}
- Field workers deployed: {stats.get('deployed_workers')}
- Field workers available for deployment: {stats.get('available_workers')}

Active Incidents:
{json.dumps(active[:10], indent=2)}

Write a professional markdown SitRep with these exact sections:
## Executive Summary
## Active Incidents
## Resource & Personnel Status
## Priority Actions (next 24 hours)
## 72-Hour Outlook

Use ## headers. Be concise, factual, and action-oriented. Do not use placeholder text."""
        return await _generate(prompt)
    except Exception as e:
        print(f"[Gemini] National report fallback: {e}")
        return _fallback_report(disasters, stats)


def _fallback_report(disasters: list, stats: dict) -> str:
    from datetime import datetime
    active = [d for d in disasters if d.get("status") == "active"]
    rows = "\n".join(
        f"| {d.get('county_name','—')} | {d.get('type','—')} | {d.get('severity','—')} | {d.get('affected_people',0):,} |"
        for d in active[:8]
    )
    return f"""## NDMA Kenya — National Situation Report
*{datetime.utcnow().strftime('%d %B %Y, %H:%M UTC')} — Auto-generated (Gemini offline)*

## Executive Summary
**{stats.get('active_disasters', len(active))} active disaster incidents** are ongoing across Kenya counties,
with an estimated **{stats.get('total_affected', 0):,} people affected**. {stats.get('deployed_workers', 0)} field
workers are currently deployed. {stats.get('high_risk_counties', 0)} counties are at elevated risk (score ≥70).

## Active Incidents

| County | Type | Severity | Affected |
|--------|------|----------|----------|
{rows}

## Resource & Personnel Status
- **Deployed:** {stats.get('deployed_workers', 0)} workers active in the field
- **Available:** {stats.get('available_workers', 0)} workers ready for immediate deployment
- **High-Risk Counties:** {stats.get('high_risk_counties', 0)} counties require priority monitoring

## Priority Actions (next 24 hours)
- Pre-position relief supplies in counties with risk score ≥ 80
- Activate water trucking for drought-affected northern counties
- Coordinate with Kenya Red Cross for medical supply replenishment
- Issue public advisories for flood-prone riverine communities

## 72-Hour Outlook
Continued monitoring of all 47 counties via automated data collection (every 30 minutes).
Connect Gemini API key for AI-powered predictive analysis and real-time threat assessment."""
