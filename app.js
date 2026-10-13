'use strict';
// ─── utilities ───────────────────────────────────────────────────────────────
const $  = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => Number(n).toFixed(2);
const mm  = s => { s = Math.max(0, Math.ceil(s)); return String(Math.floor(s/60)).padStart(2,'0') + ':' + String(s%60).padStart(2,'0'); };

// ─── state ───────────────────────────────────────────────────────────────────
let tok  = localStorage.tok  || '';
let role = localStorage.role || '';
let ST   = {};   // /api/state
let TEAMS = [];  // organizer team list
let LB1 = [], LB2 = [], LB3 = [], OVERALL = [];
let QUESTIONS = [];  // R1 questions for current team/organizer
let MY_RESULT = null;  // R1 result for team
let R2CASE = null;   // active R2 case
let MY_SUB = null;   // my R2 submission
let R3SCENE = null;  // active R3 scenario
let OD = {};   // organizer data bundle
let tab = 'status';
let quizAnswers = {};  // qid -> 'A'|'B'|'C'|'D'
let quizSubmitted = false;
let ws, timerHandle;

// ─── network ─────────────────────────────────────────────────────────────────
async function api(path, body, method) {
  const r = await fetch('/api/' + path, {
    method: body ? 'POST' : (method || 'GET'),
    headers: { 'Content-Type': 'application/json', 'x-token': tok },
    body: body ? JSON.stringify(body) : undefined
  });
  if (r.status === 401 && tok && !/login|recover/.test(path)) { logout(); throw Error('Session expired'); }
  const j = r.headers.get('content-type')?.includes('json') ? await r.json() : await r.text();
  if (!r.ok) throw Error(typeof j.detail === 'string' ? j.detail : 'Error');
  return j;
}
async function apiPut(path, body) {
  const r = await fetch('/api/' + path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'x-token': tok },
    body: JSON.stringify(body)
  });
  const j = await r.json();
  if (!r.ok) throw Error(typeof j.detail === 'string' ? j.detail : 'Error');
  return j;
}
async function apiDel(path) {
  const r = await fetch('/api/' + path, { method: 'DELETE', headers: { 'x-token': tok } });
  const j = await r.json();
  if (!r.ok) throw Error(typeof j.detail === 'string' ? j.detail : 'Error');
  return j;
}

function logout() {
  const th = localStorage.th;
  tok = ''; role = ''; localStorage.clear();
  if (th) localStorage.th = th;
  location.href = '/';
}

function toast(m, dur) {
  const t = $('#toast'); t.textContent = m; t.style.display = 'block';
  clearTimeout(toast._t); toast._t = setTimeout(() => t.style.display = 'none', dur || 3000);
}

// ─── rendering ───────────────────────────────────────────────────────────────
function H(html) { $('#app').innerHTML = html; }

function toggleTheme() {
  const t = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = t; localStorage.th = t;
}
const th0 = localStorage.th || (matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light');
document.documentElement.dataset.theme = th0;

function header(extra) {
  const statusLabel = {
    idle: 'Event Not Started', r1_open: '🟢 Round 1 – Quiz OPEN', r1_closed: '⏸ Round 1 Closed',
    r2_open: '🟢 Round 2 – Case Analysis OPEN', r2_closed: '⏸ Round 2 Closed',
    r3_open: '🟢 Round 3 – Pitch OPEN', r3_closed: '⏸ Round 3 Closed', ended: '🏆 Event Complete'
  }[ST.status] || ST.status;
  return `<header>
    <span class="brand">Bizi<span>lytics</span></span>
    <span class="pill">DoMS, Anna University</span>
    <span class="pill accent">${esc(statusLabel)}</span>
    <span class="sp"></span>
    ${extra || ''}
    <button class="g" onclick="toggleTheme()">◐</button>
    <button class="g" onclick="logout()">Logout</button>
  </header>`;
}

function statusBar() {
  const labels = {
    idle: 'Waiting for the event to begin…',
    r1_open: '⚡ ROUND 1: INSIGHT SPRINT is LIVE – answer all questions and submit before time runs out!',
    r1_closed: 'Round 1 is closed. Results being finalised.',
    r2_open: '📊 ROUND 2: DATA DETECTIVE is LIVE – analyse the case and submit your response!',
    r2_closed: 'Round 2 is closed. Judges are scoring submissions.',
    r3_open: '🎤 ROUND 3: BIZILYTICS SHOWDOWN is LIVE – prepare your pitch!',
    r3_closed: 'Round 3 complete. Judges are finalising scores.',
    ended: '🏆 THE EVENT IS COMPLETE – see Final Results!'
  };
  return `<div class="status-bar ${ST.status}">${labels[ST.status] || ST.status}</div>`;
}

// ─── landing ─────────────────────────────────────────────────────────────────
function landing(which) {
  which = which || (location.pathname === '/spectator' ? 'spec' : 'org');
  H(`<div class="land">
    <div class="logo">Bizi<span>lytics</span></div>
    <div style="font-size:13px;color:var(--mut);font-weight:700;letter-spacing:.1em;margin-bottom:2px">BATTLE</div>
    <div class="tag">Insight Sprint · Data Detective · Bizilytics Showdown</div>
    <div class="card">
      <div class="tabs">
        <button class="${which==='org'?'on':''}" onclick="landing('org')">Organizer</button>
        <button class="${which==='team'?'on':''}" onclick="landing('team')">Team</button>
        <button class="${which==='spec'?'on':''}" onclick="landing('spec')">Spectator</button>
      </div>
      ${which==='org' ? `
        <label>Username</label><input id="lu">
        <label>Password</label><input id="lp" type="password">
        <div class="err" id="le"></div>
        <button class="pri" onclick="doOrgLogin()">Login</button>` : ''}
      ${which==='team' ? `
        <h2>Register your team</h2>
        <label>Team name</label><input id="rtn" placeholder="e.g. DataMinds">
        <label>Team leader name</label><input id="rtl" placeholder="Full name">
        <label>Institution</label><input id="rti" placeholder="College / University">
        <label>Number of members (2–3)</label><input id="rtm" type="number" min="2" max="3" value="2">
        <label>Registration code <small>(if provided by organizer)</small></label><input id="rtc">
        <div class="err" id="re"></div>
        <button class="pri" onclick="doRegister()">Register &amp; Enter</button>
        <hr style="border-color:var(--bd);margin:14px 0">
        <h2>Rejoin existing team</h2>
        <div class="row">
          <input id="rii" placeholder="Team ID  e.g. T001" style="flex:1">
          <input id="ric" placeholder="Recovery code" style="flex:1">
          <button class="g" onclick="doRecover()">Recover</button>
        </div>` : ''}
      ${which==='spec' ? `
        <label>Spectator code</label><input id="sc0">
        <div class="err" id="se"></div>
        <button class="pri" onclick="doSpec()">Enter</button>` : ''}
    </div>
    <div class="wm">© Bizilytics Battle · DoMS, Anna University</div>
  </div>`);
}

const gv = id => { const e = document.getElementById(id); return e ? e.value.trim() : ''; };

async function doOrgLogin() {
  try { const j = await api('organizer/login', {username:gv('lu'), password:gv('lp')}); tok=j.token; role='organizer'; localStorage.tok=tok; localStorage.role=role; FORM={}; boot(); } catch(e) { $('#le').textContent = e.message; }
}
async function doRegister() {
  try {
    const j = await api('team/register', {name:gv('rtn'), leader:gv('rtl'), institution:gv('rti'), members:+gv('rtm')||2, code:gv('rtc')});
    tok=j.token; role='team'; localStorage.tok=tok; localStorage.role=role;
    alert(`Team registered!\nTeam ID: ${j.team_id}\nRecovery code: ${j.recovery_code}\n\nSAVE THESE – you need them to re-enter if your session expires.`);
    boot();
  } catch(e) { $('#re').textContent = e.message; }
}
async function doRecover() {
  try { const j = await api('team/recover', {team_id:gv('rii'), code:gv('ric')}); tok=j.token; role='team'; localStorage.tok=tok; localStorage.role=role; boot(); } catch(e) { toast(e.message); }
}
async function doSpec() {
  try { const j = await api('spectator/login', {code:gv('sc0')}); tok=j.token; role='spectator'; localStorage.tok=tok; localStorage.role=role; boot(); } catch(e) { $('#se').textContent=e.message; }
}

// ─── data loading ─────────────────────────────────────────────────────────────
let FORM = {};
async function refresh() {
  try {
    ST = await api('state');
    if (role === 'organizer') await loadOrgData();
    else if (role === 'team') await loadTeamData();
    else await loadSpecData();
    render();
  } catch(e) { /* keep retrying */ }
}

async function loadOrgData() {
  const [teams, lb1, lb2, lb3, overall, audit, settings] = await Promise.all([
    api('organizer/teams'),
    api('r1/leaderboard'),
    api('r2/leaderboard'),
    api('r3/leaderboard'),
    api('results'),
    api('organizer/audit'),
    api('organizer/settings'),
  ]);
  TEAMS = teams; LB1 = lb1; LB2 = lb2; LB3 = lb3;
  OVERALL = overall.overall || [];
  OD = { audit, settings };
  // load questions/cases/scenarios for management tabs
  if (tab === 'r1mgmt') QUESTIONS = await api('organizer/r1/questions').catch(() => []);
  if (tab === 'r2mgmt') {
    OD.cases = await api('organizer/r2/cases').catch(() => []);
    OD.r2subs = await api('organizer/r2/submissions').catch(() => []);
  }
  if (tab === 'r3mgmt') {
    OD.scenarios = await api('organizer/r3/scenarios').catch(() => []);
  }
}

async function loadTeamData() {
  const status = ST.status;
  if (status === 'r1_open' || status === 'r1_closed') {
    [QUESTIONS, MY_RESULT] = await Promise.all([
      api('r1/questions').catch(() => []),
      api('r1/my_result').catch(() => null)
    ]);
    if (MY_RESULT?.submitted) {
      quizSubmitted = true;
      QUESTIONS.forEach(q => { quizAnswers[q.id] = quizAnswers[q.id] || q.my_answer; });
    } else {
      QUESTIONS.forEach(q => { if (q.my_answer) quizAnswers[q.id] = q.my_answer; });
    }
  }
  if (['r2_open','r2_closed','r3_open','r3_closed','ended'].includes(status)) {
    [R2CASE, MY_SUB] = await Promise.all([
      api('r2/case').catch(() => null),
      api('r2/my_submission').catch(() => null)
    ]);
  }
  if (['r3_open','r3_closed','ended'].includes(status)) {
    R3SCENE = await api('r3/scenario').catch(() => null);
  }
  [LB1, LB2, LB3] = await Promise.all([
    api('r1/leaderboard').catch(() => []),
    api('r2/leaderboard').catch(() => []),
    api('r3/leaderboard').catch(() => [])
  ]);
}

async function loadSpecData() {
  [LB1, LB2, LB3] = await Promise.all([
    api('r1/leaderboard').catch(() => []),
    api('r2/leaderboard').catch(() => []),
    api('r3/leaderboard').catch(() => [])
  ]);
}

function connect() {
  ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
  ws.onmessage = () => refresh();
  ws.onclose = () => setTimeout(connect, 1500);
}
setInterval(() => { if (tok) refresh(); }, 8000);

// ─── timer ───────────────────────────────────────────────────────────────────
let timerStart = 0, timerDur = 0;
function startTimer(durationSec) {
  timerStart = Date.now();
  timerDur = durationSec;
  clearInterval(timerHandle);
  timerHandle = setInterval(tickTimer, 250);
}
function tickTimer() {
  const el = $('#countdown');
  if (!el) { clearInterval(timerHandle); return; }
  const rem = Math.max(0, timerDur - (Date.now() - timerStart) / 1000);
  el.textContent = mm(rem);
  el.className = 'timer-big' + (rem < 60 ? ' danger' : rem < 300 ? ' warn' : '');
}

// ─── leaderboard helpers ──────────────────────────────────────────────────────
function lbCards(rows, scoreKey, scoreLabel) {
  if (!rows || !rows.length) return '<p style="color:var(--mut)">No scores yet.</p>';
  const medals = ['🥇','🥈','🥉'];
  return rows.slice(0, 10).map((r, i) => `
    <div class="lb-row ${i===0?'top1':i===1?'top2':i===2?'top3':''}">
      <div class="lb-rank">${medals[i] || (i+1)}</div>
      <div class="lb-name">${esc(r.team || r.name)}<br><small style="color:var(--mut);font-weight:400">${esc(r.institution||'')}</small></div>
      <div class="lb-score">${r[scoreKey] ?? r.total ?? r.total_marks ?? 0} <small style="color:var(--mut);font-size:12px">${scoreLabel||'pts'}</small></div>
    </div>`).join('');
}

function lbTable(rows, cols) {
  if (!rows || !rows.length) return '<p style="color:var(--mut)">No data yet.</p>';
  const ths = cols.map(c => `<th class="${c.left?'l':''}">${c.label}</th>`).join('');
  const trs = rows.map(r => `<tr>${cols.map(c => `<td class="${c.left?'l':''}">${esc(String(r[c.key] ?? ''))}</td>`).join('')}</tr>`).join('');
  return `<table><tr>${ths}</tr>${trs}</table>`;
}

// ─── TEAM VIEWS ───────────────────────────────────────────────────────────────

// Round 1: Quiz
function quizView() {
  if (quizSubmitted && MY_RESULT?.submitted) return quizResultView();
  const total = QUESTIONS.length;
  const answered = Object.keys(quizAnswers).filter(k => quizAnswers[k]).length;
  const pct = total ? Math.round(answered / total * 100) : 0;
  const qs = QUESTIONS.map((q, i) => {
    const sel = quizAnswers[q.id];
    const opts = ['A','B','C','D'].map(l => `
      <button class="opt${sel===l?' sel':''}" onclick="selectAnswer(${q.id},'${l}')"
        ${quizSubmitted ? 'disabled' : ''}>
        <b>${l}.</b> ${esc(q['option_'+l.toLowerCase()])}
      </button>`).join('');
    return `<div class="qcard${sel?' answered':''}">
      <div class="qnum">Q${i+1} · ${esc(q.category)} · ${esc(q.difficulty)} · ${q.marks} mark${q.marks>1?'s':''}</div>
      <div class="qtext">${esc(q.text)}</div>
      <div class="options">${opts}</div>
    </div>`;
  }).join('');

  return `
    <div style="display:flex;gap:12px;align-items:center;margin-bottom:14px;flex-wrap:wrap">
      <div class="card" style="flex:1;min-width:200px">
        <h3>Progress</h3>
        <div style="font-size:22px;font-weight:800">${answered} / ${total} answered</div>
        <div style="background:var(--bd);border-radius:99px;height:8px;margin-top:8px">
          <div style="background:var(--pri);width:${pct}%;height:8px;border-radius:99px;transition:width .3s"></div>
        </div>
      </div>
      <div class="card">
        <h3>Time Remaining</h3>
        <div class="timer-big" id="countdown">--:--</div>
      </div>
      <div>
        <button class="pri" style="font-size:16px;padding:12px 24px" onclick="submitQuiz()"
          ${answered===0?'disabled':''}>
          Submit Quiz (${answered} answered)
        </button>
        <div style="color:var(--mut);font-size:12px;margin-top:4px">
          You can change answers before submitting.
        </div>
      </div>
    </div>
    ${qs}
    <div style="text-align:center;margin:20px 0">
      <button class="pri" style="font-size:16px;padding:12px 32px" onclick="submitQuiz()"
        ${answered===0?'disabled':''}>
        Submit Final Answers (${answered}/${total})
      </button>
    </div>`;
}

function quizResultView() {
  if (!MY_RESULT) return '<p>Loading result…</p>';
  const r = MY_RESULT;
  const pct = r.total_marks ? (r.total_marks / QUESTIONS.reduce((a,q)=>a+q.marks,0) * 100).toFixed(1) : 0;
  const breakdown = (r.answers || []).map((a, i) => {
    const opt = l => a['option_'+l.toLowerCase()] || '';
    const optLine = ['A','B','C','D'].map(l => {
      let cls = '';
      if (l === a.correct) cls = 'correct';
      else if (l === a.answer && a.answer !== a.correct) cls = 'wrong';
      return `<button class="opt ${cls}" disabled><b>${l}.</b> ${esc(QUESTIONS[i]?.['option_'+l.toLowerCase()] || '')}</button>`;
    }).join('');
    return `<div class="qcard ${a.is_correct?'answered':''}">
      <div class="qnum">Q${i+1} · ${a.is_correct?'<span class="up">✓ Correct</span>':a.answer?'<span class="dn">✗ Wrong</span>':'<span style="color:var(--mut)">— Skipped</span>'} · ${a.marks_awarded > 0 ? '+'+a.marks_awarded : a.marks_awarded} marks</div>
      <div class="qtext">${esc(a.text)}</div>
      <div class="options">${optLine}</div>
    </div>`;
  }).join('');
  return `
    <div class="grid g4" style="margin-bottom:16px">
      ${[['Total Score', r.total_marks + ' marks'], ['Correct', r.correct], ['Wrong', r.incorrect], ['Skipped', r.skipped]]
        .map(([l,v]) => `<div class="card kpi"><h3>${l}</h3><b>${v}</b></div>`).join('')}
    </div>
    <div class="card" style="margin-bottom:14px">
      <h2>Result submitted ✓</h2>
      <p>Your score has been recorded. The leaderboard updates as teams submit.</p>
    </div>
    ${breakdown}`;
}

async function selectAnswer(qid, letter) {
  if (quizSubmitted) return;
  quizAnswers[qid] = letter;
  // auto-save to server
  try { await api('r1/answer', {question_id: qid, answer: letter}); } catch(e) {}
  render();
}

async function submitQuiz() {
  if (quizSubmitted) return;
  if (!confirm('Submit your quiz answers? You cannot change them after submitting.')) return;
  try {
    const res = await api('r1/submit');
    MY_RESULT = { ...res, submitted: true };
    quizSubmitted = true;
    toast('Quiz submitted! Score: ' + res.total_marks + ' marks');
    await refresh();
  } catch(e) { toast(e.message); }
}

// Round 2: Case Analysis
function r2TeamView() {
  if (!R2CASE) return '<p style="color:var(--mut)">Loading case…</p>';
  const submitted = MY_SUB?.submitted;
  return `
    <div class="card" style="margin-bottom:12px">
      <h2>📋 ${esc(R2CASE.title)}</h2>
      <div class="case-block"><pre>${esc(R2CASE.description)}</pre></div>
      <h3 style="margin-top:12px">Key Data</h3>
      <div class="case-block"><pre>${esc(R2CASE.dataset_notes || '')}</pre></div>
      ${R2CASE.charts?.length ? `<h3>Referenced Charts</h3><div>${R2CASE.charts.map(c=>`<span class="data-chip">📊 ${esc(c)}</span>`).join('')}</div>` : ''}
    </div>
    <div class="card">
      <h2>${submitted ? '✅ Submission received' : 'Your Analysis'}</h2>
      ${R2CASE.questions?.map((q,i) => `<p><b>Q${i+1}.</b> ${esc(q)}</p>`).join('') || ''}
      <label><b>Key Problems Identified</b></label>
      <textarea id="kp" rows="4" ${submitted?'disabled':''}>${esc(MY_SUB?.key_problems||'')}</textarea>
      <label><b>Insights Derived</b></label>
      <textarea id="ins" rows="4" ${submitted?'disabled':''}>${esc(MY_SUB?.insights||'')}</textarea>
      <label><b>Recommended Solutions</b></label>
      <textarea id="sol" rows="4" ${submitted?'disabled':''}>${esc(MY_SUB?.solution||'')}</textarea>
      <div class="row" style="margin-top:8px">
        <button class="pri" onclick="submitCase()" ${submitted?'disabled':''}>
          ${submitted ? 'Submitted ✓' : 'Submit Analysis'}
        </button>
        ${submitted ? `<span class="badge open">Submitted</span>` : `<span style="color:var(--mut);font-size:12px">You can update until Round 2 closes.</span>`}
      </div>
      ${submitted ? `<p style="color:var(--mut);font-size:13px;margin-top:8px">Submitted at ${new Date((MY_SUB.submitted_at||0)*1000).toLocaleTimeString()}. Judges will score your submission.</p>` : ''}
    </div>
    <div class="card" style="margin-top:12px">
      <h3>Scoring Rubric</h3>
      ${Object.entries(R2CASE.rubric||{}).map(([k,v]) => `
        <div style="padding:8px 0;border-bottom:1px solid var(--bd)">
          <b>${esc(k.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase()))}</b>
          <span class="badge open" style="margin-left:8px">/${v.max}</span>
          <div style="color:var(--mut);font-size:12px;margin-top:2px">${esc(v.criteria)}</div>
        </div>`).join('')}
    </div>`;
}

async function submitCase() {
  const kp = gv('kp'), ins = gv('ins'), sol = gv('sol');
  if (!kp && !ins && !sol) { toast('Please fill in at least one field'); return; }
  try {
    await api('r2/submit', {key_problems: kp, insights: ins, solution: sol});
    toast('Analysis submitted!');
    await refresh();
  } catch(e) { toast(e.message); }
}

// Round 3: Pitch
function r3TeamView() {
  if (!R3SCENE) return '<p style="color:var(--mut)">Loading scenario…</p>';
  const prep = ST.r3_prep_sec, pres = ST.r3_pres_sec;
  return `
    <div class="card" style="margin-bottom:12px">
      <h2>🎤 ${esc(R3SCENE.title)}</h2>
      <div class="case-block"><pre>${esc(R3SCENE.description)}</pre></div>
      ${R3SCENE.context ? `<h3>Context</h3><div class="case-block"><pre>${esc(R3SCENE.context)}</pre></div>` : ''}
      ${(R3SCENE.data_points||[]).length ? `
        <h3>Key Data Points</h3>
        <div>${R3SCENE.data_points.map(d=>`<div class="data-chip">📌 ${esc(d)}</div>`).join('')}</div>` : ''}
    </div>
    <div class="grid g2">
      <div class="card">
        <h3>Preparation Time</h3>
        <div class="timer-ring"><div class="timer-big">${mm(prep)}</div><div style="color:var(--mut)">when timer starts</div></div>
      </div>
      <div class="card">
        <h3>Presentation Time</h3>
        <div class="timer-ring"><div class="timer-big" style="color:var(--sec)">${mm(pres)}</div><div style="color:var(--mut)">per team</div></div>
      </div>
    </div>
    <div class="card" style="margin-top:12px">
      <h2>Evaluation Criteria</h2>
      ${[['Creativity & Innovation',25],['Practicality of Solution',25],['Data-Driven Thinking',25],['Communication & Confidence',25]]
        .map(([l,m]) => `<div style="padding:8px 0;border-bottom:1px solid var(--bd)"><b>${l}</b> <span class="badge open">/${m}</span></div>`).join('')}
      <p style="color:var(--mut);font-size:13px">Judges may ask cross-questions to evaluate depth of understanding.</p>
    </div>`;
}

// Team view dispatcher
function teamView() {
  const status = ST.status;
  let mainContent = '';
  const tabs = [];

  if (status === 'idle') {
    mainContent = `<div class="card" style="text-align:center;padding:40px">
      <div style="font-size:48px">⏳</div>
      <h2>Waiting for the event to begin</h2>
      <p style="color:var(--mut)">The organizer will start the event shortly. Stay tuned!</p>
    </div>`;
  } else if (status === 'r1_open' || status === 'r1_closed') {
    tabs.push(['quiz','Round 1: Quiz']);
    tabs.push(['r1lb','Leaderboard']);
    if (tab === 'r1lb') mainContent = `<div class="card"><h2>Round 1 Leaderboard</h2>${lbCards(LB1,'total_marks','marks')}</div>`;
    else { tab = 'quiz'; mainContent = quizView(); }
  } else if (status === 'r2_open' || status === 'r2_closed') {
    tabs.push(['r2','Round 2: Case Analysis']);
    tabs.push(['r1lb','R1 Results']);
    tabs.push(['r2lb','R2 Leaderboard']);
    if (tab === 'r1lb') mainContent = `<div class="card"><h2>Round 1 Results</h2>${lbCards(LB1,'total_marks','marks')}</div>`;
    else if (tab === 'r2lb') mainContent = `<div class="card"><h2>Round 2 Leaderboard</h2>${lbCards(LB2,'total','pts')}</div>`;
    else { tab = 'r2'; mainContent = r2TeamView(); }
  } else if (status === 'r3_open' || status === 'r3_closed') {
    tabs.push(['r3','Round 3: Pitch']);
    tabs.push(['r1lb','R1 Results']);
    tabs.push(['r2lb','R2 Results']);
    tabs.push(['r3lb','R3 Leaderboard']);
    if (tab === 'r1lb') mainContent = `<div class="card"><h2>Round 1 Results</h2>${lbCards(LB1,'total_marks','marks')}</div>`;
    else if (tab === 'r2lb') mainContent = `<div class="card"><h2>Round 2 Results</h2>${lbCards(LB2,'total','pts')}</div>`;
    else if (tab === 'r3lb') mainContent = `<div class="card"><h2>Round 3 Leaderboard</h2>${lbCards(LB3,'total','pts')}</div>`;
    else { tab = 'r3'; mainContent = r3TeamView(); }
  } else if (status === 'ended') {
    tabs.push(['results','🏆 Final Results']);
    tabs.push(['r1lb','R1']);tabs.push(['r2lb','R2']);tabs.push(['r3lb','R3']);
    if (tab==='r1lb') mainContent=`<div class="card"><h2>Round 1 Results</h2>${lbCards(LB1,'total_marks','marks')}</div>`;
    else if (tab==='r2lb') mainContent=`<div class="card"><h2>Round 2 Results</h2>${lbCards(LB2,'total','pts')}</div>`;
    else if (tab==='r3lb') mainContent=`<div class="card"><h2>Round 3 Results</h2>${lbCards(LB3,'total','pts')}</div>`;
    else {
      tab='results';
      mainContent=`<div class="card"><h2>🏆 Final Overall Standings</h2>${lbCards(OVERALL||LB3,'total','pts')}</div>`;
    }
  }

  const tabsHtml = tabs.length ? `<div class="tabs">${tabs.map(([k,l])=>`<button class="${tab===k?'on':''}" onclick="tab='${k}';render()">${l}</button>`).join('')}</div>` : '';

  H(header() + statusBar() + `<main>${tabsHtml}${mainContent}</main><div class="wm">© Bizilytics Battle · DoMS, Anna University</div>`);

  // start countdown if quiz is open and not yet submitted
  if (status === 'r1_open' && !quizSubmitted && $('#countdown')) {
    startTimer(ST.r1_timer_sec);
  }
}

// ─── SPECTATOR VIEW ───────────────────────────────────────────────────────────
function specView() {
  const lbs = {
    r1_open:'r1',r1_closed:'r1',r2_open:'r2',r2_closed:'r2',
    r3_open:'r3',r3_closed:'r3',ended:'r3'
  };
  const primary = lbs[ST.status] || 'r1';
  const rows = primary==='r1'?LB1:primary==='r2'?LB2:LB3;
  const key = primary==='r1'?'total_marks':'total';
  const roundName = {r1:'Round 1',r2:'Round 2',r3:'Round 3'}[primary]||'';
  H(header() + statusBar() + `<main>
    <div class="grid g2">
      <div class="card"><h2>${roundName} Live Leaderboard</h2>${lbCards(rows,key,'pts')}</div>
      <div class="card">
        <h2>Event Status</h2>
        <p style="font-size:18px;font-weight:700">${esc(ST.status?.replace(/_/g,' ').toUpperCase()||'')}</p>
        <p style="color:var(--mut)">Teams: ${LB1.length}</p>
      </div>
    </div>
  </main>`);
}

// ─── ORGANIZER VIEW ───────────────────────────────────────────────────────────
function orgView() {
  const orgTabs = [
    ['status','Event Control'],['teams','Teams'],
    ['r1mgmt','Round 1 Mgmt'],['r2mgmt','Round 2 Mgmt'],['r3mgmt','Round 3 Mgmt'],
    ['lb','Leaderboards'],['settings','Settings'],['audit','Audit Log']
  ];
  const tabsHtml = `<div class="tabs">${orgTabs.map(([k,l])=>`<button class="${tab===k?'on':''}" onclick="tab='${k}';refresh()">${l}</button>`).join('')}</div>`;
  let content = '';
  if (tab==='status') content = orgStatusTab();
  else if (tab==='teams') content = orgTeamsTab();
  else if (tab==='r1mgmt') content = orgR1Tab();
  else if (tab==='r2mgmt') content = orgR2Tab();
  else if (tab==='r3mgmt') content = orgR3Tab();
  else if (tab==='lb') content = orgLbTab();
  else if (tab==='settings') content = orgSettingsTab();
  else if (tab==='audit') content = orgAuditTab();
  H(header('<span class="pill warn">ORGANIZER</span>') + statusBar() + `<main>${tabsHtml}${content}</main><div class="wm">© Bizilytics Battle · DoMS, Anna University</div>`);
}

function orgStatusTab() {
  const s = ST.status;
  const flowSteps = [
    ['idle','Not started'],['r1_open','Round 1 Open'],['r1_closed','Round 1 Closed'],
    ['r2_open','Round 2 Open'],['r2_closed','Round 2 Closed'],
    ['r3_open','Round 3 Open'],['r3_closed','Round 3 Closed'],['ended','Event Ended']
  ];
  const flow = flowSteps.map(([k,l]) => `<span class="badge ${k===s?'open':'idle'}" style="margin:2px">${l}</span>`).join(' → ');
  
  const btns = [
    ['idle','r1_open','▶ Open Round 1 (Quiz)','s'],
    ['r1_open','r1_closed','⏸ Close Round 1 & Grade','r'],
    ['r1_closed','r2_open','▶ Open Round 2 (Case Analysis)','s'],
    ['r2_open','r2_closed','⏸ Close Round 2','r'],
    ['r2_closed','r3_open','▶ Open Round 3 (Pitch)','s'],
    ['r3_open','r3_closed','⏸ Close Round 3','r'],
    ['r3_closed','ended','🏆 Finalise & End Event','s'],
  ].filter(([from]) => from === s)
   .map(([,to,label,cls]) => `<button class="${cls}" onclick="setStatus('${to}')">${label}</button>`).join('');

  const teamCount = TEAMS.length;
  const r1submitted = LB1.filter(r=>r.submitted).length;

  return `
    <div class="card">
      <h2>Event Flow</h2>
      <div style="margin-bottom:14px">${flow}</div>
      <div class="row">
        ${btns}
        <button class="r" onclick="doRestart()">🔄 Restart Everything</button>
      </div>
    </div>
    <div class="grid g4" style="margin-top:12px">
      ${[['Teams registered',teamCount],['R1 submitted',r1submitted],
         ['R2 scored',LB2.filter(r=>r.total>0).length],['R3 scored',LB3.filter(r=>r.total>0).length]]
        .map(([l,v])=>`<div class="card kpi"><h3>${l}</h3><b>${v}</b></div>`).join('')}
    </div>
    <div class="card" style="margin-top:12px">
      <h2>Export Results</h2>
      <button class="g" onclick="dlExport()">⬇ Download Full Results CSV</button>
    </div>`;
}

async function setStatus(newStatus) {
  const labels = {r1_closed:'Close Round 1 and auto-grade all teams?', ended:'Finalise and end the event?'};
  const msg = labels[newStatus] || `Set event to: ${newStatus}?`;
  if (!confirm(msg)) return;
  try {
    await api('organizer/event/set_status', {status: newStatus});
    toast('Status updated to: ' + newStatus);
    await refresh();
  } catch(e) { toast(e.message); }
}

async function doRestart() {
  const c = prompt('Type RESTART to confirm. This will erase all answers, scores, and submissions (teams stay registered).');
  if (c !== 'RESTART') { toast('Restart cancelled'); return; }
  try { await api('organizer/event/restart', {confirm:'RESTART'}); toast('Event restarted'); await refresh(); }
  catch(e) { toast(e.message); }
}

async function dlExport() {
  const r = await fetch('/api/organizer/export', {headers:{'x-token':tok}});
  const a = document.createElement('a'); a.href = URL.createObjectURL(await r.blob());
  a.download = 'bizilytics_results.csv'; a.click();
}

// Teams tab
function orgTeamsTab() {
  return `<div class="card">
    <h2>Registered Teams (${TEAMS.length})</h2>
    <table>
      <tr><th class="l">ID</th><th class="l">Name</th><th class="l">Leader</th><th class="l">Institution</th>
      <th>Members</th><th>Recovery</th><th>Status</th><th>R1</th><th>R2</th><th>R3</th><th>Actions</th></tr>
      ${TEAMS.map(t => `<tr>
        <td class="l">${t.id}</td>
        <td class="l"><b>${esc(t.name)}</b></td>
        <td class="l">${esc(t.leader)}</td>
        <td class="l">${esc(t.institution||'')}</td>
        <td>${t.members}</td>
        <td>${t.recovery}</td>
        <td><span class="badge ${t.status==='approved'?'open':'closed'}">${t.status}</span></td>
        <td>${t.r1_marks}</td><td>${t.r2_total}</td><td>${t.r3_total}</td>
        <td>
          <button class="g" onclick="toggleTeam('${t.id}','${t.status==='approved'?'deactivated':'approved'}')">${t.status==='approved'?'Deactivate':'Activate'}</button>
          <button class="r" onclick="deleteTeam('${t.id}')">🗑</button>
        </td>
      </tr>`).join('')}
    </table>
  </div>`;
}

async function toggleTeam(id, newStatus) {
  try { await api('organizer/team/'+id, {status:newStatus}); await refresh(); }
  catch(e) { toast(e.message); }
}
async function deleteTeam(id) {
  if (!confirm('Delete team '+id+'? This cannot be undone.')) return;
  try { await api('organizer/team/'+id+'/delete', {confirm_id:id}); await refresh(); }
  catch(e) { toast(e.message); }
}

// R1 Question Management
function orgR1Tab() {
  const qs = QUESTIONS;
  return `
    <div class="grid g2">
      <div class="card">
        <h2>Quiz Questions (${qs.length})</h2>
        <div style="max-height:500px;overflow:auto">
          ${qs.length ? qs.map((q,i) => `
            <div style="padding:10px;border-bottom:1px solid var(--bd)">
              <div style="display:flex;justify-content:space-between;align-items:flex-start">
                <div>
                  <b>Q${i+1}.</b> ${esc(q.text)}
                  <div style="margin-top:4px">
                    ${['A','B','C','D'].map(l=>`<span class="badge ${l===q.correct?'open':'idle'}" style="margin:1px">${l}: ${esc(q['option_'+l.toLowerCase()])}</span>`).join('')}
                  </div>
                  <div style="margin-top:4px;color:var(--mut);font-size:12px">${q.category} · ${q.difficulty} · ${q.marks}m · neg: ${q.negative_marks}</div>
                </div>
                <div style="display:flex;gap:4px;flex-shrink:0">
                  <button class="g" onclick="toggleQVis(${q.id},${q.visible})">${q.visible?'Hide':'Show'}</button>
                  <button class="r" onclick="deleteQ(${q.id})">🗑</button>
                </div>
              </div>
            </div>`).join('') : '<p style="color:var(--mut)">No questions yet.</p>'}
        </div>
      </div>
      <div class="card">
        <h2>Add Question</h2>
        <label>Question text</label><textarea id="qtext" rows="2"></textarea>
        <label>Option A</label><input id="qa">
        <label>Option B</label><input id="qb">
        <label>Option C</label><input id="qc">
        <label>Option D</label><input id="qd">
        <label>Correct answer</label>
        <select id="qcorr"><option>A</option><option>B</option><option>C</option><option>D</option></select>
        <label>Marks</label><input id="qmk" type="number" value="1" min="1">
        <label>Negative marks (0 = none)</label><input id="qneg" type="number" value="0" min="0" step="0.25">
        <label>Category</label>
        <select id="qcat">
          <option>Business Awareness</option><option>Basic Analytics</option><option>Logical Reasoning</option><option>General</option>
        </select>
        <label>Difficulty</label>
        <select id="qdiff"><option>Easy</option><option>Medium</option><option>Hard</option></select>
        <button class="pri" onclick="addQuestion()" style="margin-top:8px">Add Question</button>
        <hr style="border-color:var(--bd);margin:14px 0">
        <h3>Bulk Import (JSON)</h3>
        <p style="color:var(--mut);font-size:12px">Paste a JSON array of questions. Each needs: text, option_a, option_b, option_c, option_d, correct (A/B/C/D).</p>
        <textarea id="qjson" rows="4" placeholder='[{"text":"Q?","option_a":"A","option_b":"B","option_c":"C","option_d":"D","correct":"A"}]'></textarea>
        <button class="g" onclick="importQuestions()">Import JSON</button>
      </div>
    </div>`;
}

async function addQuestion() {
  try {
    await api('organizer/r1/questions', {
      text:gv('qtext'),option_a:gv('qa'),option_b:gv('qb'),option_c:gv('qc'),option_d:gv('qd'),
      correct:gv('qcorr'),marks:+gv('qmk')||1,negative_marks:+gv('qneg')||0,
      category:gv('qcat'),difficulty:gv('qdiff')
    });
    toast('Question added');
    await refresh();
  } catch(e) { toast(e.message); }
}
async function deleteQ(id) {
  if (!confirm('Delete question '+id+'?')) return;
  try { await apiDel('organizer/r1/questions/'+id); toast('Deleted'); await refresh(); } catch(e) { toast(e.message); }
}
async function toggleQVis(id, vis) {
  try { await apiPut('organizer/r1/questions/'+id, {visible: vis ? 0 : 1}); await refresh(); } catch(e) { toast(e.message); }
}
async function importQuestions() {
  try {
    const questions = JSON.parse(gv('qjson'));
    const res = await api('organizer/r1/import', {questions});
    toast(`Imported ${res.added} questions`);
    await refresh();
  } catch(e) { toast('Import error: ' + e.message); }
}

// R2 Case Management + Scoring
function orgR2Tab() {
  const cases = OD.cases || [];
  const subs = OD.r2subs || [];
  const active = parseInt(OD.settings?.r2_active_case || '1');
  return `
    <div class="grid g2">
      <div class="card">
        <h2>Case Selection</h2>
        ${cases.map(c => `
          <div style="padding:10px;border:1px solid var(--bd);border-radius:10px;margin-bottom:8px;${c.id===active?'border-color:var(--pri)':''}">
            <div class="row">
              <b style="flex:1">${esc(c.title)}</b>
              ${c.id===active ? '<span class="badge open">ACTIVE</span>' : `<button class="g" onclick="activateCase(${c.id})">Set Active</button>`}
            </div>
            <div style="color:var(--mut);font-size:12px;margin-top:4px">${esc(c.description.slice(0,120))}…</div>
          </div>`).join('')}
      </div>
      <div class="card">
        <h2>Team Submissions (${subs.length})</h2>
        <div style="max-height:420px;overflow:auto">
          ${subs.length ? subs.map(s => `
            <div style="padding:10px;border-bottom:1px solid var(--bd)">
              <div class="row"><b>${esc(s.team_name)}</b><span style="color:var(--mut);font-size:12px">${new Date(s.submitted_at*1000).toLocaleTimeString()}</span></div>
              <details><summary style="cursor:pointer;color:var(--mut);font-size:12px">View &amp; Score</summary>
                <div style="margin-top:8px">
                  <b>Problems:</b><p>${esc(s.key_problems)}</p>
                  <b>Insights:</b><p>${esc(s.insights)}</p>
                  <b>Solution:</b><p>${esc(s.solution)}</p>
                  ${r2ScoreForm(s.team_id)}
                </div>
              </details>
            </div>`).join('') : '<p style="color:var(--mut)">No submissions yet.</p>'}
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:12px">
      <h2>All Scores</h2>
      ${lbTable(LB2, [{key:'rank',label:'#'},{key:'name',label:'Team',left:true},{key:'analytical_thinking',label:'Analytical /40'},{key:'clarity_of_insights',label:'Clarity /30'},{key:'relevance_of_solutions',label:'Relevance /30'},{key:'total',label:'Total /100'}])}
    </div>`;
}

function r2ScoreForm(tid) {
  const existing = LB2.find(r => r.id === tid) || {};
  return `<div style="background:var(--bg);border-radius:8px;padding:10px;margin-top:8px">
    <b>Score Team</b>
    <div class="score-row"><label>Analytical Thinking <span class="score-max">/40</span></label>
      <input type="number" id="r2at_${tid}" min="0" max="40" value="${existing.analytical_thinking||0}" style="width:70px"></div>
    <div class="score-row"><label>Clarity of Insights <span class="score-max">/30</span></label>
      <input type="number" id="r2ci_${tid}" min="0" max="30" value="${existing.clarity_of_insights||0}" style="width:70px"></div>
    <div class="score-row"><label>Relevance of Solutions <span class="score-max">/30</span></label>
      <input type="number" id="r2rs_${tid}" min="0" max="30" value="${existing.relevance_of_solutions||0}" style="width:70px"></div>
    <div class="score-row"><label>Judge Notes</label>
      <input type="text" id="r2nt_${tid}" value="${esc(existing.notes||'')}" style="width:200px"></div>
    <button class="pri" style="margin-top:6px" onclick="scoreR2('${tid}')">Save Score</button>
  </div>`;
}

async function activateCase(id) {
  try { await api('organizer/r2/activate/'+id); toast('Case activated'); await refresh(); } catch(e) { toast(e.message); }
}

async function scoreR2(tid) {
  try {
    const at = parseFloat(document.getElementById('r2at_'+tid)?.value||0);
    const ci = parseFloat(document.getElementById('r2ci_'+tid)?.value||0);
    const rs = parseFloat(document.getElementById('r2rs_'+tid)?.value||0);
    const nt = document.getElementById('r2nt_'+tid)?.value||'';
    const res = await api('organizer/r2/score/'+tid, {analytical_thinking:at,clarity_of_insights:ci,relevance_of_solutions:rs,notes:nt});
    toast('R2 score saved: '+res.total);
    await refresh();
  } catch(e) { toast(e.message); }
}

// R3 Scenario Management + Scoring
function orgR3Tab() {
  const scenarios = OD.scenarios || [];
  const active = parseInt(OD.settings?.r3_active_scenario || '1');
  return `
    <div class="grid g2">
      <div class="card">
        <h2>Scenario Selection</h2>
        ${scenarios.map(s => `
          <div style="padding:10px;border:1px solid var(--bd);border-radius:10px;margin-bottom:8px;${s.id===active?'border-color:var(--pri)':''}">
            <div class="row">
              <b style="flex:1">${esc(s.title)}</b>
              ${s.id===active ? '<span class="badge open">ACTIVE</span>' : `<button class="g" onclick="activateScenario(${s.id})">Set Active</button>`}
            </div>
            <div style="color:var(--mut);font-size:12px;margin-top:4px">${esc(s.description.slice(0,120))}…</div>
          </div>`).join('')}
      </div>
      <div class="card">
        <h2>Score Teams</h2>
        <p style="color:var(--mut);font-size:13px">After each team's pitch, enter their scores below. Judges may ask cross-questions.</p>
        <div style="max-height:480px;overflow:auto">
          ${TEAMS.filter(t=>t.status==='approved').map(t => `
            <div style="padding:10px;border-bottom:1px solid var(--bd)">
              <b>${esc(t.name)}</b> <span style="color:var(--mut);font-size:12px">${esc(t.leader)}</span>
              <div style="background:var(--bg);border-radius:8px;padding:10px;margin-top:8px">
                ${r3ScoreForm(t.id)}
              </div>
            </div>`).join('')}
        </div>
      </div>
    </div>
    <div class="card" style="margin-top:12px">
      <h2>R3 Scores</h2>
      ${lbTable(LB3,[{key:'rank',label:'#'},{key:'name',label:'Team',left:true},{key:'creativity_innovation',label:'Creativity /25'},{key:'practicality_solution',label:'Practicality /25'},{key:'data_driven_thinking',label:'Data /25'},{key:'communication_confidence',label:'Comms /25'},{key:'total',label:'Total /100'}])}
    </div>`;
}

function r3ScoreForm(tid) {
  const existing = LB3.find(r => r.id === tid) || {};
  return `
    <div class="score-row"><label>Creativity &amp; Innovation <span class="score-max">/25</span></label>
      <input type="number" id="r3cr_${tid}" min="0" max="25" value="${existing.creativity_innovation||0}" style="width:70px"></div>
    <div class="score-row"><label>Practicality of Solution <span class="score-max">/25</span></label>
      <input type="number" id="r3pr_${tid}" min="0" max="25" value="${existing.practicality_solution||0}" style="width:70px"></div>
    <div class="score-row"><label>Data-Driven Thinking <span class="score-max">/25</span></label>
      <input type="number" id="r3dt_${tid}" min="0" max="25" value="${existing.data_driven_thinking||0}" style="width:70px"></div>
    <div class="score-row"><label>Communication &amp; Confidence <span class="score-max">/25</span></label>
      <input type="number" id="r3cc_${tid}" min="0" max="25" value="${existing.communication_confidence||0}" style="width:70px"></div>
    <div class="score-row"><label>Cross-Q Notes</label>
      <input type="text" id="r3cq_${tid}" value="${esc(existing.cross_question_notes||'')}" style="width:200px"></div>
    <div class="score-row"><label>General Notes</label>
      <input type="text" id="r3nt_${tid}" value="${esc(existing.notes||'')}" style="width:200px"></div>
    <button class="pri" style="margin-top:6px" onclick="scoreR3('${tid}')">Save Score</button>`;
}

async function activateScenario(id) {
  try { await api('organizer/r3/activate/'+id); toast('Scenario activated'); await refresh(); } catch(e) { toast(e.message); }
}

async function scoreR3(tid) {
  try {
    const res = await api('organizer/r3/score/'+tid, {
      creativity_innovation: parseFloat(document.getElementById('r3cr_'+tid)?.value||0),
      practicality_solution: parseFloat(document.getElementById('r3pr_'+tid)?.value||0),
      data_driven_thinking: parseFloat(document.getElementById('r3dt_'+tid)?.value||0),
      communication_confidence: parseFloat(document.getElementById('r3cc_'+tid)?.value||0),
      cross_question_notes: document.getElementById('r3cq_'+tid)?.value||'',
      notes: document.getElementById('r3nt_'+tid)?.value||''
    });
    toast('R3 score saved: '+res.total);
    await refresh();
  } catch(e) { toast(e.message); }
}

// Leaderboards tab
function orgLbTab() {
  return `
    <div class="grid g3">
      <div class="card"><h2>Round 1 – Quiz</h2>${lbCards(LB1,'total_marks','marks')}</div>
      <div class="card"><h2>Round 2 – Case Analysis</h2>${lbCards(LB2,'total','pts')}</div>
      <div class="card"><h2>Round 3 – Pitch</h2>${lbCards(LB3,'total','pts')}</div>
    </div>
    <div class="card" style="margin-top:12px">
      <h2>🏆 Overall Standings</h2>
      ${lbCards(OVERALL,'overall','total pts')}
    </div>`;
}

// Settings tab
function orgSettingsTab() {
  const se = OD.settings || {};
  const fields = [
    ['spectator_code','Spectator code'],['reg_code','Team registration code (blank = none)'],
    ['r1_timer_sec','Round 1 quiz timer (seconds)'],['r1_neg_marking','Negative marking (0=off, 1=on)'],
    ['r2_top_n','Teams advancing to Round 2 (0=all)'],['r3_top_n','Teams advancing to Round 3 (0=all)'],
    ['r2_timer_sec','Round 2 prep time (sec)'],['r2_pres_sec','Round 2 presentation time (sec)'],
    ['r3_prep_sec','Round 3 prep time (sec)'],['r3_pres_sec','Round 3 presentation time (sec)'],
  ];
  return `
    <div class="grid g2">
      <div class="card">
        <h2>Settings</h2>
        ${fields.map(([k,l]) => `<label style="font-size:12px;color:var(--mut)">${l}</label><input id="set_${k}" value="${esc(se[k]||'')}">`)
          .join('')}
        <button class="pri" onclick="saveSettings()">Save Settings</button>
      </div>
      <div class="card">
        <h2>Change Password</h2>
        <label>Current password</label><input id="oldpw" type="password">
        <label>New password</label><input id="newpw" type="password">
        <button class="g" onclick="changePw()">Change Password</button>
      </div>
    </div>`;
}

async function saveSettings() {
  const keys = ['spectator_code','reg_code','r1_timer_sec','r1_neg_marking','r2_top_n','r3_top_n',
    'r2_timer_sec','r2_pres_sec','r3_prep_sec','r3_pres_sec'];
  const b = {};
  keys.forEach(k => { const e = document.getElementById('set_'+k); if(e) b[k] = e.value; });
  try { await api('organizer/settings', b); toast('Settings saved'); await refresh(); } catch(e) { toast(e.message); }
}

async function changePw() {
  try {
    await api('organizer/password', {old: gv('oldpw'), new: gv('newpw')});
    toast('Password changed');
  } catch(e) { toast(e.message); }
}

// Audit tab
function orgAuditTab() {
  return `<div class="card">
    <h2>Audit Log</h2>
    <table>
      <tr><th>Time</th><th class="l">Actor</th><th class="l">Action</th><th class="l">Detail</th></tr>
      ${(OD.audit||[]).map(a => `<tr>
        <td>${new Date(a.ts*1000).toLocaleTimeString()}</td>
        <td class="l">${esc(a.actor)}</td>
        <td class="l">${esc(a.action)}</td>
        <td class="l" style="white-space:normal;max-width:300px">${esc(a.detail).slice(0,200)}</td>
      </tr>`).join('')}
    </table>
  </div>`;
}

// ─── main dispatcher ──────────────────────────────────────────────────────────
function render() {
  if (!role) return landing();
  if (role === 'organizer') return orgView();
  if (role === 'spectator') return specView();
  return teamView();
}

async function boot() {
  if (!tok) return landing();
  try { await api('me'); } catch(e) { return landing(); }
  if (role === 'spectator' && location.pathname !== '/spectator') history.replaceState(0,'','/spectator');
  connect();
  await refresh();
}
