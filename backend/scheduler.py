"""
scheduler.py — APScheduler background job: pulls all 4 APIs every 30 min,
updates risk scores for all 47 counties via Gemini.
"""
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

from database import (
    get_all_counties, update_county_risk, insert_disaster, fetchall
)
from data_sources import fetch_weather, fetch_earthquakes, fetch_wildfires
from gemini_service import score_county_risk

_scheduler = BackgroundScheduler(timezone="Africa/Nairobi")


def _run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _collect_and_analyse():
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n[Scheduler] ⏰ Data collection started — {now}")

    counties = await get_all_counties()
    print(f"[Scheduler] Scoring {len(counties)} counties...")

    # Score all counties — batch with small delay to respect API rate limits
    for i, county in enumerate(counties):
        weather = await fetch_weather(county["name"], county["lat"], county["lng"])
        risk    = await score_county_risk(county["name"], weather)
        await update_county_risk(county["id"], risk.get("risk_score", 0))
        if (i + 1) % 10 == 0:
            print(f"[Scheduler]   {i+1}/{len(counties)} counties scored...")
            await asyncio.sleep(1)  # brief pause every 10 to avoid rate limit

    # ── Earthquakes (USGS — no key needed) ────────────────────────────────────
    quakes = await fetch_earthquakes()
    new_quakes = 0
    for q in quakes:
        if q["magnitude"] >= 3.5:
            existing = await fetchall(
                "SELECT id FROM disasters WHERE type='Earthquake' AND ABS(lat-?)<=0.1 AND ABS(lng-?)<=0.1",
                (q["lat"], q["lng"])
            )
            if not existing:
                await insert_disaster({
                    "type":            "Earthquake",
                    "severity":        q["severity"],
                    "location":        q.get("place", "East Africa"),
                    "lat":             q["lat"],
                    "lng":             q["lng"],
                    "affected_people": 0,
                    "description":     f"M{q['magnitude']} earthquake — depth {q['depth_km']}km. {q['place']}",
                    "source":          "usgs",
                    "status":          "active",
                })
                new_quakes += 1
    if new_quakes:
        print(f"[Scheduler] 🌎 {new_quakes} new earthquake(s) auto-logged")

    # ── Wildfires (NASA FIRMS) ─────────────────────────────────────────────────
    fires = await fetch_wildfires()
    if fires:
        print(f"[Scheduler] 🔥 {len(fires)} wildfire hotspot(s) from NASA FIRMS")
        # Only log a cluster if >= 3 hotspots
        if len(fires) >= 3:
            # Group by rough 1° grid
            clusters = {}
            for f in fires:
                key = (round(f["lat"]), round(f["lng"]))
                clusters.setdefault(key, []).append(f)
            for key, pts in clusters.items():
                if len(pts) >= 3:
                    existing = await fetchall(
                        "SELECT id FROM disasters WHERE type='Wildfire' AND ABS(lat-?)<=1 AND ABS(lng-?)<=1 AND status='active'",
                        (key[0], key[1])
                    )
                    if not existing:
                        await insert_disaster({
                            "type":            "Wildfire",
                            "severity":        "High" if len(pts) >= 10 else "Medium",
                            "location":        "Northern Kenya",
                            "lat":             pts[0]["lat"],
                            "lng":             pts[0]["lng"],
                            "affected_people": 0,
                            "description":     f"{len(pts)} active fire hotspots detected via NASA FIRMS VIIRS satellite.",
                            "source":          "nasa_firms",
                            "status":          "active",
                        })

    print(f"[Scheduler] ✅ Cycle complete — {datetime.now().strftime('%H:%M:%S')}\n")


def _job():
    _run_async(_collect_and_analyse())


def start_scheduler():
    _scheduler.add_job(
        _job,
        trigger=IntervalTrigger(minutes=30),
        id="data_collection",
        name="KDMS Data Collection (All 47 Counties)",
        replace_existing=True,
    )
    _scheduler.start()
    print("[Scheduler] ✅ Started — runs every 30 min for all 47 counties")
    _job()  # Run immediately on startup


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown()
        print("[Scheduler] Stopped")
