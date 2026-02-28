"""
gemini_service.py — Production Gemini AI service for KDMS.
Only Job 5 (Chatbot) actively calls Gemini; all other jobs use local fallbacks.
"""
import os
import json
import re
import asyncio
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List
from itertools import islice
from datetime import datetime
from dotenv import load_dotenv  # type: ignore[import]

# Load .env from the same directory as this file, regardless of working directory
_here = Path(__file__).parent
load_dotenv(dotenv_path=_here.parent / ".env", override=True)

# Read key from environment after loading
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()

_model = None
_current_key: str = ""
_executor = ThreadPoolExecutor(max_workers=4)


def _init_model():
    global _model, _current_key
    # Re-read the key fresh every call so .env changes take effect on restart
    from pathlib import Path as _Path
    from dotenv import load_dotenv as _load  # type: ignore[import]
    _load(dotenv_path=_Path(__file__).parent.parent / ".env", override=True)
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    # Reset model if key has changed
    if key != _current_key:
        _model = None
        _current_key = key
    if _model is None:
        import google.generativeai as genai  # type: ignore[import]
        genai.configure(api_key=key)
        _model = genai.GenerativeModel(
            "gemini-2.5-flash",
            generation_config={"temperature": 0.3, "max_output_tokens": 1024},
        )
        safe_key = "".join(list(islice(key, max(0, len(key)-6), len(key)))) if len(key) >= 6 else "INV"
        print(f"[Gemini] Model initialised with key ...{safe_key}")
    return _model


def _extract_json(text: str) -> Any:
    """Strip markdown fences and parse JSON."""
    # Find JSON block if it exists
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        text = text.strip()
    
    # Handle trailing commas
    text = re.sub(r",\s*([}\]])", r"\1", text)
    
    try:
        return json.loads(text)
    except Exception as e:
        print(f"[Gemini] JSON Parse Error: {e}\nRaw Text:\n{text}")
        # Return fallback empty structure depending on expected type
        return [] if text.startswith("[") else {}


async def _generate(prompt: str) -> str:
    """Run Gemini generation in a thread pool (it's synchronous SDK)."""
    model = _init_model()
    if not model:
        raise RuntimeError("Gemini API key not configured")
    loop = asyncio.get_event_loop()
    try:
        resp = await loop.run_in_executor(_executor, model.generate_content, prompt)
        return resp.text
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower() or "rate" in err.lower():
            # Quick wait for a single retry if hit by an automated background task
            await asyncio.sleep(5)
            try:
                resp = await loop.run_in_executor(_executor, model.generate_content, prompt)
                return resp.text
            except Exception as e2:
                # If it fails again, bubble it up to the caller to handle (or fail gracefully)
                raise e2
        raise e


# ── Job 1: County Risk Scoring ───────────────────────────────────────────────

async def score_county_risk(county: str, weather: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyse weather data and output a structured risk score for a county.
    Returns: {risk_score, disaster_type, confidence, reasoning}
    """
    # Force use of fallback algorithm for all 47 counties to prevent 
    # exhausting the free-tier Gemini API quota (15 RPM limits), 
    # reserving the quota solely for the Chatbot and SMS generator.
    return _fallback_risk(county, weather)

def _fallback_risk(county: str, weather: Dict[str, Any]) -> Dict[str, Any]:
    rainfall: float = float(weather.get("rainfall_mm", 0))
    temp: float = float(weather.get("temp_c", 25))
    score = min(100, int(rainfall * 2.5 + max(0, int(temp) - 32) * 1.5 + random.randint(0, 15)))
    dtype = "Flood" if rainfall > 20 else "Drought" if temp > 36 and rainfall < 2 else "None"
    return {
        "risk_score":    score,
        "disaster_type": dtype,
        "confidence":    "Low",
        "reasoning":     f"Auto-calculated from rainfall={rainfall:.1f}mm, temp={temp:.1f}°C (Gemini bypassing rate limits).",
    }


# ── Job 2: 72hr Predictive Warning ───────────────────────────────────────────

async def generate_72hr_prediction(county_forecasts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Analyse 7-day forecasts and return counties at risk within 72 hours.
    Returns: [{county, threat, probability, estimated_time, recommended_action}]
    """
    # Force use of fallback algorithm to prevent exhausting the free-tier 
    # Gemini API quota (15 RPM limits), reserving the quota solely for the Chatbot.
    return _fallback_prediction(county_forecasts)

def _fallback_prediction(county_forecasts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    predictions: List[Dict[str, Any]] = []
    forecasts_slice = list(islice(county_forecasts, 20))
    for fc in forecasts_slice:
        daily: Dict[str, Any] = fc.get("forecast", {})
        precip_raw = daily.get("precipitation_sum", [])
        temp_raw = daily.get("temperature_2m_max", [])
        precip: List[float] = [float(x) for x in precip_raw]
        temp_max: List[float] = [float(x) for x in temp_raw]

        precip_3d = list(islice(precip, 3))
        temp_3d = list(islice(temp_max, 3))
        rainfall_3d: float = sum(precip_3d) if precip_3d else 0.0
        max_temp: float = max(temp_3d) if temp_3d else 25.0

        if rainfall_3d > 25:
            predictions.append({
                "county": fc["county"],
                "threat": "Flood",
                "probability": "High" if rainfall_3d > 50 else "Medium",
                "estimated_time": "within 48hrs",
                "recommended_action": "Issue advanced flood warning to riverine communities."
            })
        elif max_temp > 35 and rainfall_3d < 2:
            predictions.append({
                "county": fc["county"],
                "threat": "Drought",
                "probability": "Medium",
                "estimated_time": "within 72hrs",
                "recommended_action": "Monitor water sources and escalate tracking."
            })
    return predictions


# ── Job 3: SMS Alert Generation ───────────────────────────────────────────────

async def generate_sms_alert(disaster: Dict[str, Any], refuges: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Generate bilingual SMS alert (English + Swahili), strictly under 160 chars each.
    Returns: {english, swahili}
    """
    refuge_names = ", ".join(r["name"] for r in islice(refuges, 2)) if refuges else "nearest county offices"
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


# ── Job 4: National Situation Report ─────────────────────────────────────────

async def generate_national_report(disasters: List[Dict[str, Any]], stats: Dict[str, Any]) -> str:
    """
    Generate a professional NDMA national situation report in markdown.
    Returns: formatted markdown string.
    """
    active = [d for d in disasters if d.get("status") == "active"]
    prompt = f"""You are the NDMA Kenya National Operations Centre AI system.
Generate a formal Situation Report (SitRep) for senior NDMA officers and Cabinet Secretary.

Date: {datetime.utcnow().strftime('%d %B %Y, %H:%M UTC')}

Current National Status:
- Active disaster incidents: {stats.get('active_disasters')}
- Total estimated affected population: {stats.get('total_affected', 0):,}
- Counties at elevated risk (score ≥70): {stats.get('high_risk_counties')}
- Field workers deployed: {stats.get('deployed_workers')}
- Field workers available for deployment: {stats.get('available_workers')}

Active Incidents:
{json.dumps(list(islice(active, 10)), indent=2)}

Write a professional markdown SitRep with these exact sections:
## Executive Summary
## Active Incidents
## Resource & Personnel Status
## Priority Actions (next 24 hours)
## 72-Hour Outlook

Use ## headers. Be concise, factual, and action-oriented. Do not use placeholder text."""
    return await _generate(prompt)

# ── Job 5: Administrator Support Chatbot ─────────────────────────────────────

async def get_admin_chat_response(messages: List[Dict[str, Any]], stats: Dict[str, Any]) -> str:
    """
    Provide context-aware support for system administrators.
    messages format: [{"role": "user"|"assistant", "content": "..."}]
    """
    try:
        # Build conversation history
        history = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        
        prompt = f"""You are the KDMS (Kenya Disaster Management System) AI Assistant.
You are helping the system administrator navigate the dashboard and manage disasters.

Current System Context:
- Active disasters: {stats.get('active_disasters')}
- Total affected: {stats.get('total_affected', 0):,}
- High risk counties: {stats.get('high_risk_counties')}
- Workers: {stats.get('deployed_workers')} deployed, {stats.get('available_workers')} available

Conversation History:
{history}

Respond to the final USER message as the KDMS assistant. Be helpful, concise, and professional. You can guide them to check the "Live Map", "Risk Scores", "Workers", or "Alert Console" tabs depending on their question. Use markdown formatting sparingly. Do not hallucinate statistics outside of the context provided."""
        
        return await _generate(prompt)
    except Exception as e:
        print(f"[Gemini] Chatbot fallback: {e}")
        if "429" in str(e) or "quota" in str(e).lower():
            return "⚠️ **Gemini API Rate Limit Exceeded:** The free tier key provided (15 Requests/Min) has been exhausted. Please wait a few minutes for the quota to reset, or upgrade your Google AI Studio plan to continue using the Chatbot."
        return f"⚠️ **Connection Error:** Backend could not reach Gemini API ({str(e)})."
