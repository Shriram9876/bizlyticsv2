"""
Bizilytics Event Platform – FastAPI backend
Rounds: Insight Sprint (Quiz) → Data Detective (Case) → Bizilytics Showdown (Pitch)
"""
import asyncio, json, os, secrets, time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

import database as D
import auth
import seed_data
import scoring as S

BASE = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title="Bizilytics")

C = D.conn()
D.init(C)
seed_data.seed(C)

clients: set = set()


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def audit(actor, action, detail=""):
    C.execute(
        "INSERT INTO audit(ts,actor,action,detail) VALUES(?,?,?,?)",
        (time.time(), actor, action, detail)
    )


async def broadcast():
    msg = json.dumps({"type": "update"})
    for ws in list(clients):
        try:
            await ws.send_text(msg)
        except Exception:
            clients.discard(ws)


def need(req: Request, *roles):
    s = auth.who(C, req.headers.get("x-token"))
    if not s or s["role"] not in roles:
        raise HTTPException(401, "Not authorised")
    if s["role"] == "team":
        if not C.execute("SELECT 1 FROM teams WHERE id=?", (s["ref"],)).fetchone():
            raise HTTPException(401, "Team no longer exists")
    return s


def get_status():
    return D.get(C, "status", "idle")


# ─────────────────────────────────────────────────────────────────────────────
# auth endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/organizer/login")
async def org_login(b: dict):
    u = C.execute("SELECT * FROM users WHERE username=?", (b.get("username", ""),)).fetchone()
    if not u or not auth.check_pw(b.get("password", ""), u["pw_hash"], u["salt"]):
        raise HTTPException(401, "Invalid username or password")
    audit(u["username"], "login")
    return {"token": auth.new_session(C, "organizer", u["username"])}


@app.post("/api/organizer/password")
async def org_pw(b: dict, req: Request):
    s = need(req, "organizer")
    if len(b.get("new", "")) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    u = C.execute("SELECT * FROM users WHERE username=?", (s["ref"],)).fetchone()
    if not auth.check_pw(b.get("old", ""), u["pw_hash"], u["salt"]):
        raise HTTPException(401, "Current password wrong")
    h, sa = auth.hash_pw(b["new"])
    C.execute("UPDATE users SET pw_hash=?,salt=? WHERE id=?", (h, sa, u["id"]))
    audit(s["ref"], "password_change")
    return {"ok": True}


@app.post("/api/team/register")
async def register(b: dict):
    name = str(b.get("name") or "").strip()
    leader = str(b.get("leader") or "").strip()
    institution = str(b.get("institution") or "").strip()
    if not name or not leader:
        raise HTTPException(400, "Team name and leader name are required")
    try:
        members = max(2, min(3, int(float(b.get("members") or 2))))
    except Exception:
        members = 2
    rc = D.get(C, "reg_code", "")
    if rc and b.get("code") != rc:
        raise HTTPException(403, "Invalid registration code")
    if C.execute("SELECT 1 FROM teams WHERE name=?", (name,)).fetchone():
        raise HTTPException(409, "Team name already registered")
    n = (C.execute("SELECT MAX(CAST(SUBSTR(id,2) AS INTEGER)) FROM teams").fetchone()[0] or 0) + 1
    tid = f"T{n:03d}"
    while C.execute("SELECT 1 FROM teams WHERE id=?", (tid,)).fetchone():
        n += 1
        tid = f"T{n:03d}"
    rec = secrets.token_hex(3).upper()
    C.execute(
        "INSERT INTO teams(id,name,leader,institution,members,recovery) VALUES(?,?,?,?,?,?)",
        (tid, name, leader, institution, members, rec)
    )
    audit(tid, "register", f"'{name}' leader={leader}")
    await broadcast()
    return {"token": auth.new_session(C, "team", tid), "team_id": tid, "recovery_code": rec}


@app.post("/api/team/recover")
async def recover(b: dict):
    t = C.execute(
        "SELECT * FROM teams WHERE id=? AND recovery=?",
        ((b.get("team_id") or "").upper(), (b.get("code") or "").upper())
    ).fetchone()
    if not t or t["status"] == "deactivated":
        raise HTTPException(401, "Invalid Team ID or recovery code (or team deactivated)")
    return {"token": auth.new_session(C, "team", t["id"]), "team_id": t["id"]}


@app.post("/api/spectator/login")
async def spec(b: dict):
    if (b.get("code") or "").strip() != D.get(C, "spectator_code"):
        raise HTTPException(401, "Invalid spectator code")
    return {"token": auth.new_session(C, "spectator")}


@app.get("/api/me")
async def me(req: Request):
    s = need(req, "organizer", "team", "spectator")
    return s


# ─────────────────────────────────────────────────────────────────────────────
# shared state
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/state")
async def state(req: Request):
    need(req, "organizer", "team", "spectator")
    status = get_status()
    active_case_id = int(D.get(C, "r2_active_case", "1"))
    active_scenario_id = int(D.get(C, "r3_active_scenario", "1"))
    case = C.execute("SELECT id,title FROM r2_cases WHERE id=?", (active_case_id,)).fetchone()
    scenario = C.execute("SELECT id,title FROM r3_scenarios WHERE id=?", (active_scenario_id,)).fetchone()
    return {
        "status": status,
        "r1_timer_sec": int(D.get(C, "r1_timer_sec", "1800")),
        "r2_timer_sec": int(D.get(C, "r2_timer_sec", "900")),
        "r2_pres_sec": int(D.get(C, "r2_pres_sec", "180")),
        "r3_prep_sec": int(D.get(C, "r3_prep_sec", "600")),
        "r3_pres_sec": int(D.get(C, "r3_pres_sec", "180")),
        "active_case": dict(case) if case else None,
        "active_scenario": dict(scenario) if scenario else None,
        "r2_top_n": int(D.get(C, "r2_top_n", "5")),
        "r3_top_n": int(D.get(C, "r3_top_n", "3")),
        "neg_marking": D.get(C, "r1_neg_marking", "0") == "1",
    }


# ─────────────────────────────────────────────────────────────────────────────
# ROUND 1 – Insight Sprint
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/r1/questions")
async def r1_questions(req: Request):
    s = need(req, "organizer", "team", "spectator")
    status = get_status()
    # teams only get questions while R1 is open
    if s["role"] == "team" and status != "r1_open":
        raise HTTPException(403, "Quiz is not open")
    rows = C.execute(
        "SELECT id,text,option_a,option_b,option_c,option_d,marks,negative_marks,category,difficulty,ord"
        " FROM r1_questions WHERE visible=1 ORDER BY ord"
    ).fetchall()
    qs = [dict(r) for r in rows]
    # organizer also gets answer key
    if s["role"] == "organizer":
        for q in qs:
            q["correct"] = C.execute("SELECT correct FROM r1_questions WHERE id=?", (q["id"],)).fetchone()["correct"]
    else:
        # attach team's existing answers if any
        tid = s["ref"]
        answers = {
            r["question_id"]: r["answer"]
            for r in C.execute("SELECT question_id,answer FROM r1_answers WHERE team_id=?", (tid,))
        }
        for q in qs:
            q["my_answer"] = answers.get(q["id"])
    return qs


@app.post("/api/r1/answer")
async def r1_answer(b: dict, req: Request):
    s = need(req, "team")
    status = get_status()
    if status != "r1_open":
        raise HTTPException(403, "Quiz is not open")
    qid = b.get("question_id")
    answer = b.get("answer")  # 'A','B','C','D' or None to clear
    if answer is not None and answer not in ("A", "B", "C", "D"):
        raise HTTPException(400, "Answer must be A, B, C or D")
    q = C.execute("SELECT id FROM r1_questions WHERE id=? AND visible=1", (qid,)).fetchone()
    if not q:
        raise HTTPException(404, "Question not found")
    C.execute(
        "INSERT INTO r1_answers(team_id,question_id,answer,submitted_at)"
        " VALUES(?,?,?,?)"
        " ON CONFLICT(team_id,question_id) DO UPDATE SET answer=excluded.answer, submitted_at=excluded.submitted_at",
        (s["ref"], qid, answer, time.time())
    )
    return {"ok": True}


@app.post("/api/r1/submit")
async def r1_submit(req: Request):
    s = need(req, "team")
    status = get_status()
    if status != "r1_open":
        raise HTTPException(403, "Quiz is not accepting submissions")
    result = S.grade_r1(C, s["ref"])
    audit(s["ref"], "r1_submit", json.dumps(result))
    await broadcast()
    return result


@app.get("/api/r1/leaderboard")
async def r1_lb(req: Request):
    s = need(req, "organizer", "team", "spectator")
    rows = S.r1_leaderboard(C)
    if s["role"] != "organizer":
        # hide answer details from teams/spectators; just show rank/name/score
        return [{"rank": r["rank"], "team": r["name"], "total_marks": r["total_marks"],
                 "submitted": r["submitted_at"] > 0} for r in rows]
    return rows


@app.get("/api/r1/my_result")
async def r1_my_result(req: Request):
    s = need(req, "team")
    res = C.execute("SELECT * FROM r1_results WHERE team_id=?", (s["ref"],)).fetchone()
    if not res:
        return {"submitted": False}
    # include per-question breakdown
    answers = [
        dict(r)
        for r in C.execute(
            "SELECT a.question_id, q.text, a.answer, q.correct, a.is_correct, a.marks_awarded, q.marks"
            " FROM r1_answers a JOIN r1_questions q ON a.question_id=q.id"
            " WHERE a.team_id=? ORDER BY q.ord",
            (s["ref"],)
        )
    ]
    return {**dict(res), "submitted": True, "answers": answers}


# ─────────────────────────────────────────────────────────────────────────────
# ROUND 2 – Data Detective
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/r2/case")
async def r2_case(req: Request):
    s = need(req, "organizer", "team", "spectator")
    status = get_status()
    if s["role"] == "team" and status not in ("r2_open", "r2_closed", "r3_open", "r3_closed", "ended"):
        raise HTTPException(403, "Round 2 is not open")
    case_id = int(D.get(C, "r2_active_case", "1"))
    c = C.execute("SELECT * FROM r2_cases WHERE id=?", (case_id,)).fetchone()
    if not c:
        raise HTTPException(404, "No active case")
    d = dict(c)
    d["charts"] = json.loads(d["charts"] or "[]")
    d["questions"] = json.loads(d["questions"] or "[]")
    d["rubric"] = json.loads(d["rubric"] or "{}")
    return d


@app.post("/api/r2/submit")
async def r2_submit(b: dict, req: Request):
    s = need(req, "team")
    status = get_status()
    if status != "r2_open":
        raise HTTPException(403, "Round 2 submissions are not open")
    case_id = int(D.get(C, "r2_active_case", "1"))
    key_problems = str(b.get("key_problems") or "").strip()
    insights = str(b.get("insights") or "").strip()
    solution = str(b.get("solution") or "").strip()
    if not key_problems and not insights and not solution:
        raise HTTPException(400, "Please provide at least one field")
    C.execute(
        "INSERT INTO r2_submissions(team_id,case_id,key_problems,insights,solution,submitted_at)"
        " VALUES(?,?,?,?,?,?)"
        " ON CONFLICT(team_id,case_id) DO UPDATE SET"
        "  key_problems=excluded.key_problems, insights=excluded.insights,"
        "  solution=excluded.solution, submitted_at=excluded.submitted_at",
        (s["ref"], case_id, key_problems, insights, solution, time.time())
    )
    audit(s["ref"], "r2_submit", f"case={case_id}")
    await broadcast()
    return {"ok": True}


@app.get("/api/r2/my_submission")
async def r2_my_sub(req: Request):
    s = need(req, "team")
    case_id = int(D.get(C, "r2_active_case", "1"))
    row = C.execute(
        "SELECT * FROM r2_submissions WHERE team_id=? AND case_id=?", (s["ref"], case_id)
    ).fetchone()
    if not row:
        return {"submitted": False}
    return {**dict(row), "submitted": True}


@app.get("/api/r2/leaderboard")
async def r2_lb(req: Request):
    s = need(req, "organizer", "team", "spectator")
    rows = S.r2_leaderboard(C)
    if s["role"] != "organizer":
        return [{"rank": r["rank"], "team": r["name"], "total": r["total"]} for r in rows]
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# ROUND 3 – Bizilytics Showdown
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/r3/scenario")
async def r3_scenario(req: Request):
    s = need(req, "organizer", "team", "spectator")
    status = get_status()
    if s["role"] == "team" and status not in ("r3_open", "r3_closed", "ended"):
        raise HTTPException(403, "Round 3 is not open")
    scenario_id = int(D.get(C, "r3_active_scenario", "1"))
    sc = C.execute("SELECT * FROM r3_scenarios WHERE id=?", (scenario_id,)).fetchone()
    if not sc:
        raise HTTPException(404, "No active scenario")
    d = dict(sc)
    d["data_points"] = json.loads(d["data_points"] or "[]")
    return d


@app.get("/api/r3/leaderboard")
async def r3_lb(req: Request):
    s = need(req, "organizer", "team", "spectator")
    rows = S.r3_leaderboard(C)
    if s["role"] != "organizer":
        return [{"rank": r["rank"], "team": r["name"], "total": r["total"]} for r in rows]
    return rows


@app.get("/api/results")
async def results(req: Request):
    need(req, "organizer", "team", "spectator")
    return {
        "r1": S.r1_leaderboard(C),
        "r2": S.r2_leaderboard(C),
        "r3": S.r3_leaderboard(C),
        "overall": S.overall_leaderboard(C),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ORGANIZER – team management
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/organizer/teams")
async def teams(req: Request):
    need(req, "organizer")
    rows = [
        dict(r)
        for r in C.execute(
            "SELECT t.id,t.name,t.leader,t.institution,t.members,t.recovery,t.status,"
            "       COALESCE(r1.total_marks,0) AS r1_marks,"
            "       COALESCE(r2.total,0) AS r2_total,"
            "       COALESCE(r3.total,0) AS r3_total,"
            "       COALESCE(r1.submitted_at,0) AS r1_submitted"
            " FROM teams t"
            " LEFT JOIN r1_results r1 ON t.id=r1.team_id"
            " LEFT JOIN r2_scores r2 ON t.id=r2.team_id"
            " LEFT JOIN r3_scores r3 ON t.id=r3.team_id"
        )
    ]
    return rows


@app.post("/api/organizer/team/{tid}")
async def team_edit(tid: str, b: dict, req: Request):
    s = need(req, "organizer")
    if "status" in b and b["status"] in ("approved", "deactivated", "pending"):
        C.execute("UPDATE teams SET status=? WHERE id=?", (b["status"], tid))
    if b.get("name"):
        C.execute("UPDATE teams SET name=? WHERE id=?", (b["name"], tid))
    if b.get("new_recovery"):
        C.execute("UPDATE teams SET recovery=? WHERE id=?", (secrets.token_hex(3).upper(), tid))
    audit(s["ref"], "team_edit", f"{tid} {b}")
    await broadcast()
    return {"ok": True}


@app.post("/api/organizer/team/{tid}/delete")
async def team_delete(tid: str, b: dict, req: Request):
    s = need(req, "organizer")
    t = C.execute("SELECT * FROM teams WHERE id=?", (tid,)).fetchone()
    if not t:
        raise HTTPException(404, "Team not found")
    if b.get("confirm_id") != tid:
        raise HTTPException(400, "Confirmation does not match")
    with D.tx(C):
        C.execute("DELETE FROM r1_answers WHERE team_id=?", (tid,))
        C.execute("DELETE FROM r1_results WHERE team_id=?", (tid,))
        C.execute("DELETE FROM r2_submissions WHERE team_id=?", (tid,))
        C.execute("DELETE FROM r2_scores WHERE team_id=?", (tid,))
        C.execute("DELETE FROM r3_scores WHERE team_id=?", (tid,))
        C.execute("DELETE FROM sessions WHERE role='team' AND ref=?", (tid,))
        C.execute("DELETE FROM teams WHERE id=?", (tid,))
    audit(s["ref"], "team_delete", f"{tid} '{t['name']}'")
    await broadcast()
    return {"ok": True, "deleted": tid}


# ─────────────────────────────────────────────────────────────────────────────
# ORGANIZER – event flow
# ─────────────────────────────────────────────────────────────────────────────

VALID_STATUSES = (
    "idle", "r1_open", "r1_closed",
    "r2_open", "r2_closed",
    "r3_open", "r3_closed", "ended"
)


@app.post("/api/organizer/event/{action}")
async def event_action(action: str, b: dict, req: Request):
    s = need(req, "organizer")
    status = get_status()

    if action == "set_status":
        new_status = b.get("status")
        if new_status not in VALID_STATUSES:
            raise HTTPException(400, f"Invalid status. Must be one of: {VALID_STATUSES}")
        # when closing R1, auto-grade all teams and rank
        if new_status == "r1_closed" and status == "r1_open":
            teams_list = C.execute("SELECT id FROM teams WHERE status='approved'").fetchall()
            for t in teams_list:
                try:
                    S.grade_r1(C, t["id"])
                except Exception:
                    pass
            S.update_r1_ranks(C)
        if new_status == "r2_closed":
            S.update_r2_ranks(C)
        D.put(C, "status", new_status)
        audit(s["ref"], "event_set_status", new_status)

    elif action == "restart":
        if b.get("confirm") != "RESTART":
            raise HTTPException(400, "Type RESTART to confirm")
        with D.tx(C):
            for tbl in ("r1_answers", "r1_results", "r2_submissions", "r2_scores", "r3_scores"):
                C.execute(f"DELETE FROM {tbl}")
            D.put(C, "status", "idle")
        audit(s["ref"], "restart")

    else:
        raise HTTPException(400, f"Unknown action: {action}")

    await broadcast()
    return {"ok": True, "status": get_status()}


# ─────────────────────────────────────────────────────────────────────────────
# ORGANIZER – question management (R1)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/organizer/r1/questions")
async def org_r1_questions(req: Request):
    need(req, "organizer")
    return [
        dict(r)
        for r in C.execute("SELECT * FROM r1_questions ORDER BY ord, id")
    ]


@app.post("/api/organizer/r1/questions")
async def org_r1_add(b: dict, req: Request):
    s = need(req, "organizer")
    required = ("text", "option_a", "option_b", "option_c", "option_d", "correct")
    for f in required:
        if not b.get(f):
            raise HTTPException(400, f"Field '{f}' is required")
    if b["correct"] not in ("A", "B", "C", "D"):
        raise HTTPException(400, "correct must be A, B, C or D")
    max_ord = C.execute("SELECT COALESCE(MAX(ord),0) FROM r1_questions").fetchone()[0]
    cur = C.execute(
        "INSERT INTO r1_questions(text,option_a,option_b,option_c,option_d,correct,marks,"
        "negative_marks,category,difficulty,ord) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (b["text"], b["option_a"], b["option_b"], b["option_c"], b["option_d"], b["correct"],
         int(b.get("marks", 1)), float(b.get("negative_marks", 0)),
         b.get("category", "General"), b.get("difficulty", "Medium"), max_ord + 1)
    )
    audit(s["ref"], "r1_add_question", str(cur.lastrowid))
    return {"ok": True, "id": cur.lastrowid}


@app.put("/api/organizer/r1/questions/{qid}")
async def org_r1_edit(qid: int, b: dict, req: Request):
    s = need(req, "organizer")
    q = C.execute("SELECT id FROM r1_questions WHERE id=?", (qid,)).fetchone()
    if not q:
        raise HTTPException(404, "Question not found")
    fields = ["text", "option_a", "option_b", "option_c", "option_d", "correct",
              "marks", "negative_marks", "category", "difficulty", "visible", "ord"]
    updates = {k: b[k] for k in fields if k in b}
    if "correct" in updates and updates["correct"] not in ("A", "B", "C", "D"):
        raise HTTPException(400, "correct must be A, B, C or D")
    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        C.execute(f"UPDATE r1_questions SET {set_clause} WHERE id=?", (*updates.values(), qid))
    audit(s["ref"], "r1_edit_question", str(qid))
    return {"ok": True}


@app.delete("/api/organizer/r1/questions/{qid}")
async def org_r1_delete(qid: int, req: Request):
    s = need(req, "organizer")
    C.execute("DELETE FROM r1_questions WHERE id=?", (qid,))
    C.execute("DELETE FROM r1_answers WHERE question_id=?", (qid,))
    audit(s["ref"], "r1_delete_question", str(qid))
    return {"ok": True}


@app.post("/api/organizer/r1/import")
async def org_r1_import(b: dict, req: Request):
    """Bulk import questions from JSON array."""
    s = need(req, "organizer")
    questions = b.get("questions", [])
    if not isinstance(questions, list):
        raise HTTPException(400, "questions must be a JSON array")
    added = 0
    max_ord = C.execute("SELECT COALESCE(MAX(ord),0) FROM r1_questions").fetchone()[0]
    for q in questions:
        try:
            required = ("text", "option_a", "option_b", "option_c", "option_d", "correct")
            if not all(q.get(f) for f in required):
                continue
            if q["correct"] not in ("A", "B", "C", "D"):
                continue
            max_ord += 1
            C.execute(
                "INSERT INTO r1_questions(text,option_a,option_b,option_c,option_d,correct,"
                "marks,negative_marks,category,difficulty,ord) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (q["text"], q["option_a"], q["option_b"], q["option_c"], q["option_d"],
                 q["correct"], int(q.get("marks", 1)), float(q.get("negative_marks", 0)),
                 q.get("category", "General"), q.get("difficulty", "Medium"), max_ord)
            )
            added += 1
        except Exception:
            continue
    audit(s["ref"], "r1_import", f"{added} questions added")
    return {"ok": True, "added": added}


# ─────────────────────────────────────────────────────────────────────────────
# ORGANIZER – case management (R2)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/organizer/r2/cases")
async def org_r2_cases(req: Request):
    need(req, "organizer")
    rows = [dict(r) for r in C.execute("SELECT * FROM r2_cases ORDER BY ord, id")]
    for r in rows:
        r["charts"] = json.loads(r["charts"] or "[]")
        r["questions"] = json.loads(r["questions"] or "[]")
        r["rubric"] = json.loads(r["rubric"] or "{}")
    return rows


@app.post("/api/organizer/r2/activate/{case_id}")
async def org_r2_activate(case_id: int, req: Request):
    s = need(req, "organizer")
    if not C.execute("SELECT 1 FROM r2_cases WHERE id=?", (case_id,)).fetchone():
        raise HTTPException(404, "Case not found")
    D.put(C, "r2_active_case", str(case_id))
    audit(s["ref"], "r2_activate_case", str(case_id))
    await broadcast()
    return {"ok": True}


@app.get("/api/organizer/r2/submissions")
async def org_r2_submissions(req: Request):
    need(req, "organizer")
    case_id = int(D.get(C, "r2_active_case", "1"))
    rows = [
        dict(r)
        for r in C.execute(
            "SELECT s.*, t.name AS team_name, t.institution"
            " FROM r2_submissions s JOIN teams t ON s.team_id=t.id"
            " WHERE s.case_id=? ORDER BY s.submitted_at",
            (case_id,)
        )
    ]
    return rows


@app.post("/api/organizer/r2/score/{team_id}")
async def org_r2_score(team_id: str, b: dict, req: Request):
    s = need(req, "organizer")
    at = float(b.get("analytical_thinking", 0))
    ci = float(b.get("clarity_of_insights", 0))
    rs = float(b.get("relevance_of_solutions", 0))
    # validate ranges
    if not (0 <= at <= 40): raise HTTPException(400, "analytical_thinking must be 0-40")
    if not (0 <= ci <= 30): raise HTTPException(400, "clarity_of_insights must be 0-30")
    if not (0 <= rs <= 30): raise HTTPException(400, "relevance_of_solutions must be 0-30")
    total = at + ci + rs
    C.execute(
        "INSERT INTO r2_scores(team_id,analytical_thinking,clarity_of_insights,"
        "relevance_of_solutions,total,notes,scored_by,scored_at)"
        " VALUES(?,?,?,?,?,?,?,?)"
        " ON CONFLICT(team_id) DO UPDATE SET"
        "  analytical_thinking=excluded.analytical_thinking,"
        "  clarity_of_insights=excluded.clarity_of_insights,"
        "  relevance_of_solutions=excluded.relevance_of_solutions,"
        "  total=excluded.total, notes=excluded.notes,"
        "  scored_by=excluded.scored_by, scored_at=excluded.scored_at",
        (team_id, at, ci, rs, total, b.get("notes", ""), s["ref"], time.time())
    )
    audit(s["ref"], "r2_score", f"{team_id} total={total}")
    return {"ok": True, "total": total}


# ─────────────────────────────────────────────────────────────────────────────
# ORGANIZER – scenario management (R3)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/organizer/r3/scenarios")
async def org_r3_scenarios(req: Request):
    need(req, "organizer")
    rows = [dict(r) for r in C.execute("SELECT * FROM r3_scenarios ORDER BY ord, id")]
    for r in rows:
        r["data_points"] = json.loads(r["data_points"] or "[]")
    return rows


@app.post("/api/organizer/r3/activate/{scenario_id}")
async def org_r3_activate(scenario_id: int, req: Request):
    s = need(req, "organizer")
    if not C.execute("SELECT 1 FROM r3_scenarios WHERE id=?", (scenario_id,)).fetchone():
        raise HTTPException(404, "Scenario not found")
    D.put(C, "r3_active_scenario", str(scenario_id))
    audit(s["ref"], "r3_activate_scenario", str(scenario_id))
    await broadcast()
    return {"ok": True}


@app.post("/api/organizer/r3/score/{team_id}")
async def org_r3_score(team_id: str, b: dict, req: Request):
    s = need(req, "organizer")
    cr = float(b.get("creativity_innovation", 0))
    pr = float(b.get("practicality_solution", 0))
    dt = float(b.get("data_driven_thinking", 0))
    cc = float(b.get("communication_confidence", 0))
    if not (0 <= cr <= 25): raise HTTPException(400, "creativity_innovation must be 0-25")
    if not (0 <= pr <= 25): raise HTTPException(400, "practicality_solution must be 0-25")
    if not (0 <= dt <= 25): raise HTTPException(400, "data_driven_thinking must be 0-25")
    if not (0 <= cc <= 25): raise HTTPException(400, "communication_confidence must be 0-25")
    total = cr + pr + dt + cc
    C.execute(
        "INSERT INTO r3_scores(team_id,creativity_innovation,practicality_solution,"
        "data_driven_thinking,communication_confidence,total,notes,cross_question_notes,scored_by,scored_at)"
        " VALUES(?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(team_id) DO UPDATE SET"
        "  creativity_innovation=excluded.creativity_innovation,"
        "  practicality_solution=excluded.practicality_solution,"
        "  data_driven_thinking=excluded.data_driven_thinking,"
        "  communication_confidence=excluded.communication_confidence,"
        "  total=excluded.total, notes=excluded.notes,"
        "  cross_question_notes=excluded.cross_question_notes,"
        "  scored_by=excluded.scored_by, scored_at=excluded.scored_at",
        (team_id, cr, pr, dt, cc, total,
         b.get("notes", ""), b.get("cross_question_notes", ""), s["ref"], time.time())
    )
    audit(s["ref"], "r3_score", f"{team_id} total={total}")
    return {"ok": True, "total": total}


# ─────────────────────────────────────────────────────────────────────────────
# ORGANIZER – settings & utilities
# ─────────────────────────────────────────────────────────────────────────────

SETTINGS_KEYS = (
    "spectator_code", "reg_code",
    "r1_timer_sec", "r1_neg_marking",
    "r2_active_case", "r2_timer_sec", "r2_pres_sec",
    "r3_active_scenario", "r3_prep_sec", "r3_pres_sec",
    "r2_top_n", "r3_top_n",
)


@app.get("/api/organizer/settings")
async def get_settings(req: Request):
    need(req, "organizer")
    return {k: D.get(C, k) for k in SETTINGS_KEYS}


@app.post("/api/organizer/settings")
async def save_settings(b: dict, req: Request):
    s = need(req, "organizer")
    applied = {}
    for k in SETTINGS_KEYS:
        if k not in b:
            continue
        v = str(b[k])
        D.put(C, k, v)
        applied[k] = v
    audit(s["ref"], "settings", json.dumps(applied))
    await broadcast()
    return {"ok": True, "applied": applied}


@app.get("/api/organizer/audit")
async def audit_log(req: Request):
    need(req, "organizer")
    return [
        dict(r)
        for r in C.execute("SELECT ts,actor,action,detail FROM audit ORDER BY id DESC LIMIT 50")
    ]


@app.get("/api/organizer/export")
async def export_results(req: Request):
    need(req, "organizer")
    overall = S.overall_leaderboard(C)
    csv_lines = ["Rank,Team,Institution,R1 Score,R2 Score,R3 Score,Overall Score"]
    for r in overall:
        csv_lines.append(
            f'{r["rank"]},"{r["name"]}","{r.get("institution","")}",{r["r1_score"]},{r["r2_score"]},{r["r3_score"]},{r["overall"]}'
        )
    csv_lines.append("\nRound 1 Detail")
    csv_lines.append("Rank,Team,Total Marks,Correct,Incorrect,Skipped,Advanced to R2")
    for r in S.r1_leaderboard(C):
        csv_lines.append(
            f'{r["rank"]},"{r["name"]}",{r["total_marks"]},{r["correct"]},{r["incorrect"]},{r["skipped"]},{r["advanced"]}'
        )
    csv_lines.append("\nRound 2 Detail")
    csv_lines.append("Rank,Team,Analytical Thinking,Clarity of Insights,Relevance of Solutions,Total,Advanced to R3")
    for r in S.r2_leaderboard(C):
        csv_lines.append(
            f'{r["rank"]},"{r["name"]}",{r["analytical_thinking"]},{r["clarity_of_insights"]},{r["relevance_of_solutions"]},{r["total"]},{r["advanced"]}'
        )
    csv_lines.append("\nRound 3 Detail")
    csv_lines.append("Rank,Team,Creativity,Practicality,Data-Driven,Communication,Total")
    for r in S.r3_leaderboard(C):
        csv_lines.append(
            f'{r["rank"]},"{r["name"]}",{r["creativity_innovation"]},{r["practicality_solution"]},{r["data_driven_thinking"]},{r["communication_confidence"]},{r["total"]}'
        )
    csv_lines.append("\n© Bizilytics – DoMS Anna University")
    return Response(
        "\n".join(csv_lines),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bizilytics_results.csv"}
    )


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket + static files
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def ws(w: WebSocket):
    await w.accept()
    clients.add(w)
    try:
        while True:
            await w.receive_text()
    except WebSocketDisconnect:
        clients.discard(w)


app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")


@app.get("/")
@app.get("/spectator")
async def index():
    return FileResponse(os.path.join(BASE, "static", "index.html"))


if __name__ == "__main__":
    import uvicorn, socket
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "YOUR-IP"
    print(f"\nBizilytics Event Platform\n"
          f" Organizer:  http://localhost:8000\n"
          f" Teams:      http://{ip}:8000\n"
          f" Spectator:  http://{ip}:8000/spectator\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
