import sqlite3, threading, os

DB_PATH = os.environ.get("BIZILYTICS_DB", os.path.join(os.path.dirname(__file__), "bizilytics.db"))
LOCK = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    pw_hash TEXT,
    salt TEXT
);

CREATE TABLE IF NOT EXISTS teams(
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE COLLATE NOCASE,
    leader TEXT,
    institution TEXT,
    members INTEGER DEFAULT 2,
    recovery TEXT,
    status TEXT DEFAULT 'approved'
);

CREATE TABLE IF NOT EXISTS sessions(
    token TEXT PRIMARY KEY,
    role TEXT,
    ref TEXT,
    created REAL
);

CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);

-- ─── ROUND 1: Insight Sprint (Quiz) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS r1_questions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct TEXT NOT NULL,           -- 'A','B','C','D'
    marks INTEGER DEFAULT 1,
    negative_marks REAL DEFAULT 0,
    category TEXT DEFAULT 'General',
    difficulty TEXT DEFAULT 'Medium',
    visible INTEGER DEFAULT 1,
    ord INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS r1_answers(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    question_id INTEGER NOT NULL,
    answer TEXT,                     -- 'A','B','C','D' or NULL if skipped
    is_correct INTEGER DEFAULT 0,
    marks_awarded REAL DEFAULT 0,
    submitted_at REAL,
    UNIQUE(team_id, question_id)
);

CREATE TABLE IF NOT EXISTS r1_results(
    team_id TEXT PRIMARY KEY,
    total_marks REAL DEFAULT 0,
    correct INTEGER DEFAULT 0,
    incorrect INTEGER DEFAULT 0,
    skipped INTEGER DEFAULT 0,
    submitted_at REAL,
    rank INTEGER DEFAULT 0,
    advanced INTEGER DEFAULT 0       -- 1 = moves to Round 2
);

-- ─── ROUND 2: Data Detective (Case Analysis) ────────────────────────────────
CREATE TABLE IF NOT EXISTS r2_cases(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,       -- problem statement / context
    dataset_notes TEXT,              -- dataset summary / key figures
    charts TEXT,                     -- JSON array of chart descriptions
    questions TEXT,                  -- JSON array of sub-questions
    rubric TEXT,                     -- JSON scoring rubric
    visible INTEGER DEFAULT 1,
    ord INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS r2_submissions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    case_id INTEGER NOT NULL,
    key_problems TEXT,               -- team's identified problems (text)
    insights TEXT,                   -- derived insights (text)
    solution TEXT,                   -- suggested solution (text)
    submitted_at REAL,
    UNIQUE(team_id, case_id)
);

CREATE TABLE IF NOT EXISTS r2_scores(
    team_id TEXT PRIMARY KEY,
    analytical_thinking REAL DEFAULT 0,  -- /40
    clarity_of_insights REAL DEFAULT 0,  -- /30
    relevance_of_solutions REAL DEFAULT 0, -- /30
    total REAL DEFAULT 0,
    notes TEXT,
    rank INTEGER DEFAULT 0,
    advanced INTEGER DEFAULT 0,       -- 1 = moves to Round 3
    scored_by TEXT,
    scored_at REAL
);

-- ─── ROUND 3: Bizilytics Showdown (Final Pitch) ─────────────────────────────
CREATE TABLE IF NOT EXISTS r3_scenarios(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    context TEXT,
    data_points TEXT,                -- JSON key figures
    visible INTEGER DEFAULT 1,
    ord INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS r3_scores(
    team_id TEXT PRIMARY KEY,
    creativity_innovation REAL DEFAULT 0,   -- /25
    practicality_solution REAL DEFAULT 0,   -- /25
    data_driven_thinking REAL DEFAULT 0,    -- /25
    communication_confidence REAL DEFAULT 0,-- /25
    total REAL DEFAULT 0,
    cross_question_notes TEXT,
    notes TEXT,
    rank INTEGER DEFAULT 0,
    scored_by TEXT,
    scored_at REAL
);

CREATE TABLE IF NOT EXISTS audit(
    id INTEGER PRIMARY KEY,
    ts REAL,
    actor TEXT,
    action TEXT,
    detail TEXT
);
"""


def conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init(c):
    c.executescript(SCHEMA)


def get(c, k, d=None):
    r = c.execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
    return r["v"] if r else d


def put(c, k, v):
    c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))


from contextlib import contextmanager

@contextmanager
def tx(c):
    """Atomic transaction; nests safely inside an already-open one."""
    if c.in_transaction:
        yield
        return
    c.execute("BEGIN IMMEDIATE")
    try:
        yield
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise
