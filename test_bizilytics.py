"""
Bizilytics test suite.
Run: pytest tests/test_bizilytics.py -v
"""
import json, os, sys, time, tempfile
import pytest

# Point DB at a temp file for tests
tmp = tempfile.mktemp(suffix='.db')
os.environ['BIZILYTICS_DB'] = tmp

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import database as D, auth, seed_data, scoring as S

from fastapi.testclient import TestClient
from server import app

client = TestClient(app, raise_server_exceptions=False)


# ─── helpers ─────────────────────────────────────────────────────────────────
def org_token():
    r = client.post('/api/organizer/login', json={'username':'organizer','password':'admin123'})
    assert r.status_code == 200, r.text
    return r.json()['token']


def register_team(name='TestTeam', leader='Leader A', tok_org=None):
    r = client.post('/api/team/register', json={'name':name,'leader':leader,'institution':'Test U','members':2})
    assert r.status_code == 200, r.text
    return r.json()


def team_token(name='TeamAlpha'):
    j = register_team(name)
    return j['token'], j['team_id']


# ─── auth tests ──────────────────────────────────────────────────────────────
class TestAuth:
    def test_org_login_ok(self):
        r = client.post('/api/organizer/login', json={'username':'organizer','password':'admin123'})
        assert r.status_code == 200
        assert 'token' in r.json()

    def test_org_login_wrong_pw(self):
        r = client.post('/api/organizer/login', json={'username':'organizer','password':'wrong'})
        assert r.status_code == 401

    def test_team_register(self):
        j = register_team('RegTeam','Leader B')
        assert j['team_id'].startswith('T')
        assert len(j['recovery_code']) == 6

    def test_team_duplicate_name(self):
        register_team('UniqueTeam', 'L1')
        r = client.post('/api/team/register', json={'name':'UniqueTeam','leader':'L2','members':2})
        assert r.status_code == 409

    def test_team_recovery(self):
        j = register_team('RecoverMe', 'L1')
        r = client.post('/api/team/recover', json={'team_id':j['team_id'],'code':j['recovery_code']})
        assert r.status_code == 200
        assert 'token' in r.json()

    def test_spectator_login(self):
        r = client.post('/api/spectator/login', json={'code':'SPECTATE'})
        assert r.status_code == 200

    def test_no_token_rejected(self):
        r = client.get('/api/state')
        assert r.status_code == 401

    def test_me_endpoint(self):
        tok = org_token()
        r = client.get('/api/me', headers={'x-token': tok})
        assert r.status_code == 200
        assert r.json()['role'] == 'organizer'


# ─── state tests ─────────────────────────────────────────────────────────────
class TestState:
    def test_state_initial(self):
        tok = org_token()
        r = client.get('/api/state', headers={'x-token':tok})
        assert r.status_code == 200
        data = r.json()
        assert data['status'] == 'idle'

    def test_set_status_r1_open(self):
        tok = org_token()
        r = client.post('/api/organizer/event/set_status', json={'status':'r1_open'}, headers={'x-token':tok})
        assert r.status_code == 200

    def test_set_invalid_status(self):
        tok = org_token()
        r = client.post('/api/organizer/event/set_status', json={'status':'invalid'}, headers={'x-token':tok})
        assert r.status_code == 400


# ─── Round 1 tests ────────────────────────────────────────────────────────────
class TestRound1:
    @pytest.fixture(autouse=True)
    def open_r1(self):
        tok = org_token()
        # ensure idle first
        client.post('/api/organizer/event/set_status', json={'status':'idle'}, headers={'x-token':tok})
        client.post('/api/organizer/event/set_status', json={'status':'r1_open'}, headers={'x-token':tok})
        yield
        # close after
        client.post('/api/organizer/event/set_status', json={'status':'r1_closed'}, headers={'x-token':tok})

    def test_team_can_get_questions(self):
        tt, _ = team_token('QuizTeam1')
        r = client.get('/api/r1/questions', headers={'x-token':tt})
        assert r.status_code == 200
        qs = r.json()
        assert len(qs) >= 20

    def test_team_can_answer(self):
        tt, _ = team_token('QuizTeam2')
        qs = client.get('/api/r1/questions', headers={'x-token':tt}).json()
        first_q = qs[0]
        r = client.post('/api/r1/answer', json={'question_id':first_q['id'],'answer':'A'}, headers={'x-token':tt})
        assert r.status_code == 200

    def test_invalid_answer_rejected(self):
        tt, _ = team_token('QuizTeam3')
        qs = client.get('/api/r1/questions', headers={'x-token':tt}).json()
        r = client.post('/api/r1/answer', json={'question_id':qs[0]['id'],'answer':'X'}, headers={'x-token':tt})
        assert r.status_code == 400

    def test_submit_grades_correctly(self):
        tt, tid = team_token('GradeTeam')
        qs = client.get('/api/r1/questions', headers={'x-token':tt}).json()
        # get correct answers from organizer
        otok = org_token()
        org_qs = client.get('/api/organizer/r1/questions', headers={'x-token':otok}).json()
        correct_map = {q['id']: q['correct'] for q in org_qs}
        # answer all questions correctly
        for q in qs:
            correct = correct_map.get(q['id'])
            if correct:
                client.post('/api/r1/answer', json={'question_id':q['id'],'answer':correct}, headers={'x-token':tt})
        r = client.post('/api/r1/submit', headers={'x-token':tt})
        assert r.status_code == 200
        result = r.json()
        assert result['correct'] == len(qs)
        assert result['total_marks'] == sum(q['marks'] for q in qs)

    def test_leaderboard_accessible(self):
        tok = org_token()
        r = client.get('/api/r1/leaderboard', headers={'x-token':tok})
        assert r.status_code == 200

    def test_organizer_can_add_question(self):
        tok = org_token()
        r = client.post('/api/organizer/r1/questions', json={
            'text':'What is 2+2?','option_a':'3','option_b':'4','option_c':'5','option_d':'6',
            'correct':'B','marks':1,'negative_marks':0,'category':'Logical Reasoning','difficulty':'Easy'
        }, headers={'x-token':tok})
        assert r.status_code == 200
        assert r.json()['ok']

    def test_organizer_can_delete_question(self):
        tok = org_token()
        qs = client.get('/api/organizer/r1/questions', headers={'x-token':tok}).json()
        # add one to delete
        add = client.post('/api/organizer/r1/questions', json={
            'text':'Delete me','option_a':'A','option_b':'B','option_c':'C','option_d':'D','correct':'A'
        }, headers={'x-token':tok})
        qid = add.json()['id']
        r = client.delete(f'/api/organizer/r1/questions/{qid}', headers={'x-token':tok})
        assert r.status_code == 200

    def test_bulk_import(self):
        tok = org_token()
        questions = [
            {'text':f'Imported Q{i}','option_a':'A','option_b':'B','option_c':'C','option_d':'D','correct':'A'}
            for i in range(3)
        ]
        r = client.post('/api/organizer/r1/import', json={'questions':questions}, headers={'x-token':tok})
        assert r.status_code == 200
        assert r.json()['added'] == 3


# ─── Round 2 tests ────────────────────────────────────────────────────────────
class TestRound2:
    @pytest.fixture(autouse=True)
    def open_r2(self):
        tok = org_token()
        client.post('/api/organizer/event/set_status', json={'status':'r1_closed'}, headers={'x-token':tok})
        client.post('/api/organizer/event/set_status', json={'status':'r2_open'}, headers={'x-token':tok})
        yield
        client.post('/api/organizer/event/set_status', json={'status':'r2_closed'}, headers={'x-token':tok})

    def test_team_gets_case(self):
        tt, _ = team_token('CaseTeam1')
        r = client.get('/api/r2/case', headers={'x-token':tt})
        assert r.status_code == 200
        case = r.json()
        assert 'title' in case
        assert 'description' in case

    def test_team_can_submit(self):
        tt, _ = team_token('CaseTeam2')
        r = client.post('/api/r2/submit', json={
            'key_problems':'Problem 1, Problem 2',
            'insights':'Insight based on data',
            'solution':'Recommended action'
        }, headers={'x-token':tt})
        assert r.status_code == 200

    def test_organizer_can_score(self):
        tt, tid = team_token('ScoredTeam2')
        client.post('/api/r2/submit', json={'key_problems':'P','insights':'I','solution':'S'}, headers={'x-token':tt})
        otok = org_token()
        r = client.post(f'/api/organizer/r2/score/{tid}', json={
            'analytical_thinking':30,'clarity_of_insights':20,'relevance_of_solutions':25,'notes':'Good'
        }, headers={'x-token':otok})
        assert r.status_code == 200
        assert r.json()['total'] == 75

    def test_r2_score_out_of_range(self):
        tt, tid = team_token('BadScore2')
        otok = org_token()
        r = client.post(f'/api/organizer/r2/score/{tid}', json={
            'analytical_thinking':50,'clarity_of_insights':10,'relevance_of_solutions':10
        }, headers={'x-token':otok})
        assert r.status_code == 400

    def test_organizer_can_activate_case(self):
        otok = org_token()
        cases = client.get('/api/organizer/r2/cases', headers={'x-token':otok}).json()
        if len(cases) >= 2:
            r = client.post(f"/api/organizer/r2/activate/{cases[1]['id']}", headers={'x-token':otok})
            assert r.status_code == 200


# ─── Round 3 tests ────────────────────────────────────────────────────────────
class TestRound3:
    @pytest.fixture(autouse=True)
    def open_r3(self):
        tok = org_token()
        client.post('/api/organizer/event/set_status', json={'status':'r2_closed'}, headers={'x-token':tok})
        client.post('/api/organizer/event/set_status', json={'status':'r3_open'}, headers={'x-token':tok})
        yield
        client.post('/api/organizer/event/set_status', json={'status':'r3_closed'}, headers={'x-token':tok})

    def test_team_gets_scenario(self):
        tt, _ = team_token('PitchTeam1')
        r = client.get('/api/r3/scenario', headers={'x-token':tt})
        assert r.status_code == 200
        sc = r.json()
        assert 'title' in sc
        assert 'description' in sc

    def test_organizer_can_score_r3(self):
        tt, tid = team_token('ScoredTeam3')
        otok = org_token()
        r = client.post(f'/api/organizer/r3/score/{tid}', json={
            'creativity_innovation':20,'practicality_solution':22,
            'data_driven_thinking':18,'communication_confidence':24,
            'notes':'Excellent pitch','cross_question_notes':'Handled Q well'
        }, headers={'x-token':otok})
        assert r.status_code == 200
        assert r.json()['total'] == 84

    def test_r3_score_out_of_range(self):
        tt, tid = team_token('BadScore3')
        otok = org_token()
        r = client.post(f'/api/organizer/r3/score/{tid}', json={
            'creativity_innovation':30,'practicality_solution':20,'data_driven_thinking':20,'communication_confidence':20
        }, headers={'x-token':otok})
        assert r.status_code == 400

    def test_activate_scenario(self):
        otok = org_token()
        scenarios = client.get('/api/organizer/r3/scenarios', headers={'x-token':otok}).json()
        if len(scenarios) >= 2:
            r = client.post(f"/api/organizer/r3/activate/{scenarios[1]['id']}", headers={'x-token':otok})
            assert r.status_code == 200


# ─── results & leaderboard ────────────────────────────────────────────────────
class TestResults:
    def test_overall_leaderboard(self):
        tok = org_token()
        r = client.get('/api/results', headers={'x-token':tok})
        assert r.status_code == 200
        data = r.json()
        assert 'r1' in data
        assert 'r2' in data
        assert 'r3' in data
        assert 'overall' in data

    def test_export_csv(self):
        tok = org_token()
        r = client.get('/api/organizer/export', headers={'x-token':tok})
        assert r.status_code == 200
        assert 'text/csv' in r.headers.get('content-type','')
        content = r.text
        assert 'Bizilytics' in content

    def test_audit_log(self):
        tok = org_token()
        r = client.get('/api/organizer/audit', headers={'x-token':tok})
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ─── permissions ─────────────────────────────────────────────────────────────
class TestPermissions:
    def test_team_cannot_access_org_endpoints(self):
        tt, _ = team_token('PermTeam')
        r = client.get('/api/organizer/teams', headers={'x-token':tt})
        assert r.status_code == 401

    def test_spectator_cannot_submit_quiz(self):
        r = client.post('/api/spectator/login', json={'code':'SPECTATE'})
        st = r.json()['token']
        rs = client.post('/api/r1/submit', headers={'x-token':st})
        assert rs.status_code == 401

    def test_team_blocked_from_closed_quiz(self):
        # ensure status is idle (quiz not open)
        otok = org_token()
        client.post('/api/organizer/event/set_status', json={'status':'idle'}, headers={'x-token':otok})
        tt, _ = team_token('BlockedTeam')
        r = client.get('/api/r1/questions', headers={'x-token':tt})
        assert r.status_code == 403

    def test_organizer_cannot_submit_quiz(self):
        tok = org_token()
        r = client.post('/api/r1/submit', headers={'x-token':tok})
        assert r.status_code == 401


# ─── settings ─────────────────────────────────────────────────────────────────
class TestSettings:
    def test_get_settings(self):
        tok = org_token()
        r = client.get('/api/organizer/settings', headers={'x-token':tok})
        assert r.status_code == 200
        data = r.json()
        assert 'r1_timer_sec' in data

    def test_save_settings(self):
        tok = org_token()
        r = client.post('/api/organizer/settings', json={'r1_timer_sec':'1800','spectator_code':'NEWCODE'}, headers={'x-token':tok})
        assert r.status_code == 200
        # verify
        r2 = client.get('/api/organizer/settings', headers={'x-token':tok})
        assert r2.json()['spectator_code'] == 'NEWCODE'
