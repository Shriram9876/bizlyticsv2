# Bizilytics Battle – Event Platform

A fully-functional web application for running the **Bizilytics Battle** management fest event at DoMS, Anna University. Built on the FINestra architecture, adapted and extended to run all three rounds of Bizilytics Battle.

---

## Event Structure

| Round | Name | Format | Scoring |
|---|---|---|---|
| 1 | **Insight Sprint** | MCQ Quiz (timed) | Auto-graded (correct/incorrect/skipped) |
| 2 | **Data Detective** | Case Analysis (written submission) | Judge-scored (100 pts) |
| 3 | **Bizilytics Showdown** | Pitch Presentation | Judge-scored (100 pts) |

---

## Quick Start

### Requirements
- Python 3.10 or later
- No database setup needed — SQLite is used automatically

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the server

```bash
python server.py
```

The server will print:
```
Bizilytics Event Platform
 Organizer:  http://localhost:8000
 Teams:      http://192.168.x.x:8000
 Spectator:  http://192.168.x.x:8000/spectator
```

- **Organizer panel** → open `http://localhost:8000` in the organizer's browser
- **Team registration & quiz** → share `http://<your-ip>:8000` with all teams (same WiFi)
- **Spectator view** → share `http://<your-ip>:8000/spectator`

### Default login

| Role | Username | Password |
|---|---|---|
| Organizer | `organizer` | `admin123` |

**Change the password immediately** via Settings → Change Password.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `BIZILYTICS_DB` | `bizilytics.db` (same folder) | Path to the SQLite database file |

Example:
```bash
BIZILYTICS_DB=/data/bizilytics.db python server.py
```

---

## Running Tests

```bash
pytest tests/test_bizilytics.py -v
```

All 37 tests cover: auth, team registration, R1 quiz answering & auto-grading, R2 case submission & judge scoring, R3 scenario & judge scoring, leaderboards, permissions, settings, CSV export, and audit log.

---

## Organizer Guide

### Before the event

1. **Log in** at `http://localhost:8000` with `organizer` / `admin123`
2. **Change password** (Settings tab)
3. **Set spectator code** (Settings tab) — share with audience
4. **Set registration code** (Settings tab, optional) — if you want to restrict who registers
5. **Review questions** (Round 1 Mgmt tab) — 25 questions preloaded, add/remove/edit as needed
6. **Choose the active case** (Round 2 Mgmt tab) — 3 cases preloaded
7. **Choose the active scenario** (Round 3 Mgmt tab) — 3 scenarios preloaded
8. **Configure timers** (Settings tab) — defaults: R1 = 30 min, R2 prep = 15 min, R3 prep = 10 min

### Running the event

#### Round 1 – Insight Sprint (Quiz)

1. Click **▶ Open Round 1 (Quiz)** in Event Control
2. Teams register at `http://<ip>:8000` → answer 25 MCQs → Submit
3. Answers auto-save as teams select them (recovery safe)
4. Click **⏸ Close Round 1 & Grade** — all teams are auto-graded and ranked
5. View R1 leaderboard in the Leaderboards tab

#### Round 2 – Data Detective (Case Analysis)

1. Choose the active case (Round 2 Mgmt tab) — set before opening round
2. Click **▶ Open Round 2 (Case Analysis)**
3. Teams read the case (dataset, charts, questions) and submit written analysis
4. After submissions close, click **⏸ Close Round 2**
5. In Round 2 Mgmt tab → view each submission → enter scores:
   - Analytical Thinking (0–40)
   - Clarity of Insights (0–30)
   - Relevance of Solutions (0–30)
6. Click **Save Score** for each team

#### Round 3 – Bizilytics Showdown (Pitch)

1. Choose the active scenario (Round 3 Mgmt tab)
2. Click **▶ Open Round 3 (Pitch)** — teams see the scenario
3. Teams prepare offline; present to judges in person
4. In Round 3 Mgmt tab → enter scores for each team:
   - Creativity & Innovation (0–25)
   - Practicality of Solution (0–25)
   - Data-Driven Thinking (0–25)
   - Communication & Confidence (0–25)
   - Cross-question notes (free text)
5. Click **Save Score** for each team

#### End the event

1. Click **🏆 Finalise & End Event** — overall leaderboard appears for all roles
2. **Download Full Results CSV** (Event Control tab) — complete breakdown

---

## Question Management (Round 1)

### Preloaded questions (25 total)

| Category | Count |
|---|---|
| Business Awareness | 10 |
| Basic Analytics | 10 |
| Logical Reasoning | 5 |

### Add a question

Round 1 Mgmt tab → fill the form → **Add Question**

### Bulk import (JSON)

Paste a JSON array into the Import field:

```json
[
  {
    "text": "What is the capital of India?",
    "option_a": "Mumbai",
    "option_b": "New Delhi",
    "option_c": "Kolkata",
    "option_d": "Chennai",
    "correct": "B",
    "marks": 1,
    "negative_marks": 0,
    "category": "Business Awareness",
    "difficulty": "Easy"
  }
]
```

Fields `marks`, `negative_marks`, `category`, `difficulty` are optional (defaults: 1, 0, General, Medium).

### Negative marking

Set **Negative marking** to `1` in Settings to enable. `negative_marks` per question controls the deduction (default: 0 per question means no deduction even when enabled globally).

---

## Preloaded Cases (Round 2)

| # | Title | Theme |
|---|---|---|
| 1 | RetailCo's Declining Sales Mystery | Retail analytics, footfall, e-commerce |
| 2 | FinTech Fraud Detection Challenge | Fraud pattern analysis, risk strategy |
| 3 | GreenGrow Expansion Decision | Agri-tech market entry, funding choice |

---

## Preloaded Scenarios (Round 3)

| # | Title | Theme |
|---|---|---|
| 1 | EduSpark – Scaling a Vernacular EdTech | Growth strategy, unit economics |
| 2 | UrbanBite – Ghost Kitchen Turnaround | Operational turnaround, P&L recovery |
| 3 | CleanDrive – EV Charging Network Strategy | Market entry, business model choice |

---

## Role Guide

### Organizer
- Full event control, scoring, team management
- Can add/edit/delete R1 questions
- Can bulk-import questions (JSON)
- Can choose active case (R2) and scenario (R3)
- Scores R2 and R3 submissions
- Exports CSV results

### Team
- Registers with name, leader, institution, member count
- Round 1: answers quiz, submits, sees result with per-question breakdown
- Round 2: reads case, submits written analysis (can update before close)
- Round 3: reads pitch scenario, prepares offline, presents to judges
- Can recover session with Team ID + recovery code

### Spectator
- Read-only live leaderboard view
- Accessed at `/spectator` with spectator code

---

## Architecture

```
bizilytics/
├── server.py          # FastAPI backend, all API endpoints
├── database.py        # SQLite schema, connection, helpers
├── auth.py            # PBKDF2 password hashing, session tokens
├── seed_data.py       # Default questions, cases, scenarios, settings
├── scoring.py         # Auto-grading (R1), leaderboard computation
├── requirements.txt
├── README.md
├── static/
│   ├── index.html     # Single-page app shell
│   └── app.js         # Full frontend (vanilla JS, no framework)
└── tests/
    └── test_bizilytics.py  # 37 pytest tests
```

### Key design decisions

- **Single SQLite file** — no setup, no separate DB server, backup by copying one file
- **WebSocket push** — all browsers update instantly when the organizer changes status or scores a team
- **Auto-save quiz answers** — each option click saves to the server; teams don't lose progress on refresh
- **Auto-grading on R1 close** — closing R1 triggers server-side grading for all teams simultaneously
- **Role-based API** — every endpoint checks the token role; teams cannot see other teams' submissions or organizer data

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Teams can't reach the server | Check firewall; share `http://<lan-ip>:8000` not `localhost` |
| "Session expired" on refresh | Team uses recovery code (Team ID + recovery code) to re-enter |
| Quiz not showing for team | Organizer must click ▶ Open Round 1 first |
| Score not updating | Refresh; scores push via WebSocket but fallback polling is every 8 seconds |
| Need to redo the event | Event Control → 🔄 Restart Everything (type `RESTART` to confirm) |

---

## Known Limitations / Not Implemented

- **File upload for R2 submissions** — teams submit text only; they cannot attach a spreadsheet or slide. Organizers can ask teams to share files separately.
- **Timer enforcement** — the R1 timer is a display-only countdown. The server does not auto-close Round 1 when the timer hits zero; the organizer must click Close Round 1. This is intentional — it gives organisers flexibility.
- **PDF/Excel import for questions** — only JSON bulk import is supported. To import from Excel, export to CSV → convert to JSON via a script or online tool.
- **Multiple judges** — all organizer accounts share one login. For multi-judge events, share the organizer credentials or extend the user table.
- **Cross-question scoring in R3** — there is no separate numeric field for cross-questions; use the free-text notes field and factor it into the four rubric scores.

---

*© Bizilytics Battle · Department of Management Studies, Anna University – College of Engineering Guindy, Chennai*
