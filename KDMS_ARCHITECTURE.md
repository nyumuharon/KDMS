# KDMS — Kenya Disaster Management System
## Full System Architecture

---

## ANSWER: Where does data come from & how does Gemini fit?

### DATA SOURCES (Real APIs, Free Tier)
| Source | What it gives you | API |
|---|---|---|
| **OpenWeatherMap** | Rainfall, storms, extreme heat — Kenya counties | api.openweathermap.org (free 1000 calls/day) |
| **NASA FIRMS** | Active wildfires from satellite (MODIS/VIIRS) | firms.modaps.eosdis.nasa.gov (free) |
| **USGS Earthquake API** | Real-time quake data for East Africa | earthquake.usgs.gov/fdsnws (free, no key) |
| **Open-Meteo** | 7-day weather forecast per lat/lng, no key needed | api.open-meteo.com (free, unlimited) |
| **Field Workers (Your App)** | Manual reports from ground — floods, landslides, droughts | Your own POST /report endpoint |

### HOW GEMINI API IS USED (5 Specific Jobs)
1. **Risk Scoring** — Gemini reads raw weather JSON + satellite fire data → outputs structured risk score per county
2. **Situation Report Generation** — Gemini writes a human-readable briefing for NDMA officers from raw data
3. **Worker Dispatch Recommendation** — Gemini analyzes disaster location + available workers → recommends who to send
4. **Community Alert Writing** — Gemini writes the SMS alert in English + Swahili, plain language, under 160 chars
5. **Predictive Warning** — Gemini reads 7-day forecast → flags counties likely to flood/drought in next 72hrs

---

## SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION LAYER                     │
│                                                                 │
│  OpenWeatherMap ──┐                                             │
│  NASA FIRMS ──────┼──► Data Collector (runs every 30 min)      │
│  USGS Earthquakes ┤    (Python background scheduler)           │
│  Open-Meteo ──────┘         │                                   │
│                             ▼                                   │
│                     SQLite / PostgreSQL DB                      │
│                     (disasters, workers, alerts, counties)      │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                       AI PROCESSING LAYER                       │
│                                                                 │
│   Raw Data → Gemini 1.5 Flash API → Structured JSON output     │
│                                                                 │
│   Jobs:                                                         │
│   • Risk score per county (0-100)                              │
│   • "Disaster likely in Tana River in 48hrs" prediction        │
│   • Situation report for NDMA officers                         │
│   • SMS alert text (English + Swahili)                         │
│   • Worker dispatch recommendation                             │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                        FASTAPI BACKEND                          │
│                                                                 │
│  GET  /disasters          - all active/past disasters           │
│  GET  /counties/risk      - risk score per county (Gemini)     │
│  POST /report             - field worker submits disaster       │
│  POST /dispatch           - assign worker to disaster           │
│  POST /alert/send         - trigger SMS to affected community  │
│  GET  /predict            - 72hr AI forecast (Gemini)          │
│  GET  /report/national    - full NDMA briefing (Gemini)        │
│  GET  /workers            - worker status + locations          │
└─────────────────────────────┬───────────────────────────────────┘
                              │
          ┌───────────────────┴────────────────────┐
          │                                        │
┌─────────▼─────────┐                  ┌──────────▼──────────┐
│   REACT DASHBOARD │                  │  AFRICA'S TALKING   │
│   (NDMA Officers) │                  │  SMS API            │
│                   │                  │                     │
│  • Live map       │                  │  • Bulk SMS to      │
│  • Risk heatmap   │                  │    community phones │
│  • Worker tracker │                  │  • English+Swahili  │
│  • AI reports     │                  │  • Refuge locations │
│  • Alert console  │                  │  • ~KES 0.80/SMS    │
└───────────────────┘                  └─────────────────────┘
          │
┌─────────▼─────────┐
│  MOBILE-FRIENDLY  │
│  FIELD WORKER APP │
│  (same React app) │
│                   │
│  • Submit report  │
│  • See assignment │
│  • Offline-first  │
└───────────────────┘
```

---

## DATABASE SCHEMA (SQLite for hackathon, PostgreSQL for production)

```sql
-- Counties with risk scores
counties (id, name, region, lat, lng, risk_score, last_updated)

-- Disasters (auto-detected + manual)
disasters (id, type, severity, county_id, location, lat, lng,
           affected_people, description, source, status,
           reported_at, resolved_at)

-- Refuge sites per county
refuge_sites (id, name, county_id, lat, lng, capacity, type)

-- Field workers
workers (id, name, role, phone, county_id, status,
         current_disaster_id, lat, lng)

-- SMS alerts sent
alerts (id, disaster_id, message_en, message_sw,
        recipients_count, sent_at, status)

-- AI analysis cache (avoid re-calling Gemini for same data)
ai_cache (id, disaster_id, analysis_json, generated_at)
```

---

## GEMINI PROMPT DESIGN (The Core Logic)

### Prompt 1 — Risk Scoring (runs every 30 min)
```
Input: weather JSON for county X
Output: { risk_score: 78, disaster_type: "Flood",
          confidence: "High", reasoning: "..." }
```

### Prompt 2 — 72hr Prediction
```
Input: 7-day forecast for all 47 counties
Output: [{ county, threat, probability, estimated_time,
           recommended_action }]
```

### Prompt 3 — SMS Alert (English + Swahili, <160 chars)
```
Input: disaster details + refuge sites
Output: { english: "...", swahili: "..." }
```

### Prompt 4 — National Situation Report
```
Input: all active disasters + stats
Output: formatted markdown report for NDMA
```

---

## FILE STRUCTURE

```
kdms/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── database.py          # SQLite setup + queries
│   ├── scheduler.py         # APScheduler — pulls APIs every 30min
│   ├── data_sources.py      # OpenWeatherMap, FIRMS, USGS fetchers
│   ├── gemini_service.py    # All Gemini API calls in one place
│   ├── sms_service.py       # Africa's Talking integration
│   ├── seed_data.py         # Kenya counties + refuge sites + workers
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main dashboard
│   │   ├── MapView.jsx      # Leaflet map with disaster pins
│   │   ├── RiskPanel.jsx    # County risk heatmap
│   │   ├── WorkerPanel.jsx  # Worker dispatch console
│   │   ├── AlertConsole.jsx # SMS alert sender
│   │   └── AIReport.jsx     # Gemini report viewer
│   └── package.json
├── .env                     # GEMINI_API_KEY, OPENWEATHER_KEY, AT_KEY
└── README.md
```

---

## BUILD ORDER FOR 10 HOURS

| Hour | Task |
|---|---|
| 0-1 | Set up FastAPI + SQLite + seed Kenya data (47 counties, workers, refuge sites) |
| 1-2 | Connect OpenWeatherMap + USGS + NASA FIRMS fetchers |
| 2-3 | Build Gemini service (risk scoring + SMS generation) |
| 3-4 | Build all API endpoints |
| 4-5 | React dashboard shell + Leaflet map |
| 5-6 | Risk panel + disaster cards |
| 6-7 | Worker dispatch UI |
| 7-8 | Alert console + SMS flow |
| 8-9 | AI report page + polish |
| 9-10 | Test end-to-end, fix bugs, prepare demo |

---

## ENV VARIABLES NEEDED

```
GEMINI_API_KEY=AIza...          # console.cloud.google.com (free $300 credit)
OPENWEATHER_API_KEY=...         # openweathermap.org (free tier)
AFRICASTALKING_USERNAME=...     # africastalking.com (sandbox is free)
AFRICASTALKING_API_KEY=...
NASA_FIRMS_MAP_KEY=...          # firms.modaps.eosdis.nasa.gov (free)
```
