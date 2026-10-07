import os
import subprocess
from pathlib import Path


def test_dynamic_dashboard_add_expense_and_qr(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("DATASET_DIR", str((Path(__file__).parents[1] / "dataset").resolve()))
    monkeypatch.setenv("RESULT_DIR", str(tmp_path / "natija"))
    code = r'''
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    health = client.get('/health')
    assert health.json() == {'status':'ok','database':'ok'}
    assert "default-src 'self'" in health.headers['content-security-policy']
    groups = client.get('/api/groups').json()
    assert len(groups) == 81
    group_id = groups[0]['id']
    members = client.get(f'/api/groups/{group_id}/members').json()
    ids = [member['id'] for member in members[:3]]
    payer = ids[0]
    before = client.get('/api/dashboard', params={'group_id':group_id,'member_id':payer}).json()['member_balance']
    response = client.post('/api/expenses', json={
        'group_id':group_id,'paid_by':payer,'amount':10,'category':'test','note':'',
        'method':'teng','participants':ids
    })
    assert response.status_code == 201, response.text
    after = client.get('/api/dashboard', params={'group_id':group_id,'member_id':payer}).json()['member_balance']
    payer_share = 10 // len(ids) + (1 if sorted(ids).index(payer) < 10 % len(ids) else 0)
    assert after == before + 10 - payer_share
    qr = client.get('/api/qr', params={'sender':'U1','receiver':'U2','amount':10})
    assert qr.status_code == 200 and qr.headers['content-type'] == 'image/png'
    unknown = client.post('/api/expenses', json={
        'group_id':'missing','paid_by':'nobody','amount':10,'category':'test','note':'test',
        'method':'teng','participants':['nobody']
    })
    assert unknown.status_code == 400
    unknown_settlement = client.post('/api/settlements', json={
        'group_id':'missing','sender_id':'a','receiver_id':'b','amount':10
    })
    assert unknown_settlement.status_code == 404
    cross_site = client.post('/api/expenses', headers={'Origin':'https://evil.example'}, json={
        'group_id':'G0001','paid_by':'U000001','amount':10,'category':'test','note':'test',
        'method':'teng','participants':['U000001']
    })
    assert cross_site.status_code == 403
    duplicate_upload = client.post('/api/import', files=[
        ('files', ('groups.csv', b'bad', 'text/csv')) for _ in range(5)
    ])
    assert duplicate_upload.status_code == 400
'''
    result = subprocess.run([os.sys.executable, "-c", code], env=os.environ.copy(), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
