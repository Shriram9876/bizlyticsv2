"""
Scoring helpers for all three Bizilytics rounds.
"""
import time
import database as D


# ─────────────────────────────────────────────────────────────────────────────
# ROUND 1 – Insight Sprint (auto-graded quiz)
# ─────────────────────────────────────────────────────────────────────────────

def grade_r1(c, team_id: str) -> dict:
    """Grade a team's R1 answers and upsert r1_results. Returns result dict."""
    neg_on = D.get(c, "r1_neg_marking", "0") == "1"
    questions = {
        r["id"]: r
        for r in c.execute("SELECT id,correct,marks,negative_marks FROM r1_questions WHERE visible=1")
    }
    answers = {
        r["question_id"]: r
        for r in c.execute(
            "SELECT question_id,answer FROM r1_answers WHERE team_id=?", (team_id,)
        )
    }
    total = correct = incorrect = skipped = 0
    for qid, q in questions.items():
        ans = answers.get(qid)
        if ans is None or ans["answer"] is None:
            skipped += 1
            c.execute(
                "INSERT INTO r1_answers(team_id,question_id,answer,is_correct,marks_awarded,submitted_at)"
                " VALUES(?,?,NULL,0,0,?) ON CONFLICT(team_id,question_id) DO NOTHING",
                (team_id, qid, time.time())
            )
        elif ans["answer"] == q["correct"]:
            correct += 1
            total += q["marks"]
            c.execute(
                "UPDATE r1_answers SET is_correct=1,marks_awarded=? WHERE team_id=? AND question_id=?",
                (q["marks"], team_id, qid)
            )
        else:
            incorrect += 1
            deduct = q["negative_marks"] if neg_on else 0
            total -= deduct
            c.execute(
                "UPDATE r1_answers SET is_correct=0,marks_awarded=? WHERE team_id=? AND question_id=?",
                (-deduct, team_id, qid)
            )

    total = max(0, total)
    c.execute(
        "INSERT INTO r1_results(team_id,total_marks,correct,incorrect,skipped,submitted_at)"
        " VALUES(?,?,?,?,?,?)"
        " ON CONFLICT(team_id) DO UPDATE SET"
        "  total_marks=excluded.total_marks, correct=excluded.correct,"
        "  incorrect=excluded.incorrect, skipped=excluded.skipped, submitted_at=excluded.submitted_at",
        (team_id, total, correct, incorrect, skipped, time.time())
    )
    return dict(total_marks=total, correct=correct, incorrect=incorrect, skipped=skipped)


def r1_leaderboard(c) -> list:
    """Ranked R1 leaderboard."""
    rows = [
        dict(r)
        for r in c.execute(
            "SELECT t.id, t.name, t.institution, COALESCE(r.total_marks,0) AS total_marks,"
            "       COALESCE(r.correct,0) AS correct, COALESCE(r.incorrect,0) AS incorrect,"
            "       COALESCE(r.skipped,0) AS skipped, COALESCE(r.submitted_at,0) AS submitted_at,"
            "       COALESCE(r.advanced,0) AS advanced"
            " FROM teams t LEFT JOIN r1_results r ON t.id=r.team_id"
            " WHERE t.status='approved'"
            " ORDER BY total_marks DESC, submitted_at ASC"
        )
    ]
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def update_r1_ranks(c):
    lb = r1_leaderboard(c)
    top_n = int(D.get(c, "r2_top_n", "0"))
    for r in lb:
        advanced = 1 if (top_n == 0 or r["rank"] <= top_n) else 0
        c.execute(
            "UPDATE r1_results SET rank=?, advanced=? WHERE team_id=?",
            (r["rank"], advanced, r["id"])
        )


# ─────────────────────────────────────────────────────────────────────────────
# ROUND 2 – Data Detective (judge-scored)
# ─────────────────────────────────────────────────────────────────────────────

def r2_leaderboard(c) -> list:
    rows = [
        dict(r)
        for r in c.execute(
            "SELECT t.id, t.name, t.institution,"
            "       COALESCE(s.analytical_thinking,0) AS analytical_thinking,"
            "       COALESCE(s.clarity_of_insights,0) AS clarity_of_insights,"
            "       COALESCE(s.relevance_of_solutions,0) AS relevance_of_solutions,"
            "       COALESCE(s.total,0) AS total,"
            "       COALESCE(s.notes,'') AS notes,"
            "       COALESCE(s.advanced,0) AS advanced"
            " FROM teams t LEFT JOIN r2_scores s ON t.id=s.team_id"
            " WHERE t.status='approved'"
            " ORDER BY total DESC"
        )
    ]
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def update_r2_ranks(c):
    lb = r2_leaderboard(c)
    top_n = int(D.get(c, "r3_top_n", "0"))
    for r in lb:
        advanced = 1 if (top_n == 0 or r["rank"] <= top_n) else 0
        c.execute(
            "INSERT INTO r2_scores(team_id,advanced) VALUES(?,?)"
            " ON CONFLICT(team_id) DO UPDATE SET advanced=excluded.advanced, rank=?",
            (r["id"], advanced, r["rank"])
        )
        c.execute("UPDATE r2_scores SET rank=? WHERE team_id=?", (r["rank"], r["id"]))


# ─────────────────────────────────────────────────────────────────────────────
# ROUND 3 – Bizilytics Showdown (judge-scored)
# ─────────────────────────────────────────────────────────────────────────────

def r3_leaderboard(c) -> list:
    rows = [
        dict(r)
        for r in c.execute(
            "SELECT t.id, t.name, t.institution,"
            "       COALESCE(s.creativity_innovation,0) AS creativity_innovation,"
            "       COALESCE(s.practicality_solution,0) AS practicality_solution,"
            "       COALESCE(s.data_driven_thinking,0) AS data_driven_thinking,"
            "       COALESCE(s.communication_confidence,0) AS communication_confidence,"
            "       COALESCE(s.total,0) AS total,"
            "       COALESCE(s.notes,'') AS notes,"
            "       COALESCE(s.cross_question_notes,'') AS cross_question_notes"
            " FROM teams t LEFT JOIN r3_scores s ON t.id=s.team_id"
            " WHERE t.status='approved'"
            " ORDER BY total DESC"
        )
    ]
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def overall_leaderboard(c) -> list:
    """Combined leaderboard: R1 + R2 + R3 weighted."""
    r1 = {r["id"]: r for r in r1_leaderboard(c)}
    r2 = {r["id"]: r for r in r2_leaderboard(c)}
    r3 = {r["id"]: r for r in r3_leaderboard(c)}
    teams = [dict(r) for r in c.execute("SELECT id,name,institution FROM teams WHERE status='approved'")]
    for t in teams:
        tid = t["id"]
        r1s = r1.get(tid, {}).get("total_marks", 0)
        r2s = r2.get(tid, {}).get("total", 0)
        r3s = r3.get(tid, {}).get("total", 0)
        t["r1_score"] = round(r1s, 2)
        t["r2_score"] = round(r2s, 2)
        t["r3_score"] = round(r3s, 2)
        t["overall"] = round(r1s + r2s + r3s, 2)
    teams.sort(key=lambda x: -x["overall"])
    for i, t in enumerate(teams, 1):
        t["rank"] = i
    return teams
