from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_flow


def test_manual_translation_link_uses_scoped_current_inventory(monkeypatch):
    app=Flask(__name__)
    app.secret_key='test-only'
    blueprint=Blueprint('translation_m2',__name__)
    reports_flow.register(blueprint)
    app.register_blueprint(blueprint)
    first='11111111-1111-4111-8111-111111111111'
    second='22222222-2222-4222-8222-222222222222'
    monkeypatch.setattr(reports_flow,'_selection',lambda *_:{'client_id':7})
    monkeypatch.setattr(reports_flow,'_write_guard',lambda *_:None)
    monkeypatch.setattr(reports_flow,'_flow_row',lambda *_:{'id':'flow','tag_id':'tag'})
    calls=[]
    def rows(sql, params=()):
        calls.append((sql,params))
        if 'SELECT id,path_prefix' in sql:
            return [{'id':first,'path_prefix':'/contato','locale':'pt'},
                    {'id':second,'path_prefix':'/en/contact','locale':'en'}]
        return []
    class Database:
        def commit(self):pass
    monkeypatch.setattr(reports_flow,'_rows',rows)
    monkeypatch.setattr(reports_flow,'get_db',lambda:Database())
    client=app.test_client()
    with client.session_transaction() as session:session['user_id']=1
    response=client.post('/api/v2/reports/flow/flows/flow/translations',json={
        'page_id':first,'translation_page_id':second})
    assert response.status_code==200
    assert response.json['translation_key']=='/contato'
    assert any('run_id=(SELECT id' in sql for sql,_ in calls)
    assert any('UPDATE cadu_reports_flow_discovered_pages' in sql and params[0]=='/contato' for sql,params in calls)
