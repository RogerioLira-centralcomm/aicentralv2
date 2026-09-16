"""Local-only preview with test fixtures; never connects to the database."""
from flask import session
from tests.test_cadu_family import FamilyTest
from unittest.mock import patch

fixture = FamilyTest()
fixture.setUp()
app = fixture.app
fixture.actor.return_value = {**fixture.actor.return_value, 'name': 'Pessoa com nome longo para validar navegação'}
fixture.clients.return_value[0]['name'] = 'Agência de comunicação com nome extenso para teste de contexto'
patch('aicentralv2.cadu_family.chat.modes', return_value=[{'id':'ideias','title':'Ideias e organização'}]).start()
patch('aicentralv2.cadu_family.repository.get_db', side_effect=RuntimeError('Preview must never access database')).start()
patch('aicentralv2.cadu_family.repository.conversation_history', return_value=[]).start()
patch('aicentralv2.cadu_workspace.conversations.attachments.upload', return_value={'id':'demo-file','name':'attachment-demo.txt','kind':'document','size':55}).start()
patch('aicentralv2.cadu_family.chat.prepare', return_value={}).start()
patch('aicentralv2.cadu_family.chat.stream', return_value=iter([
    'data: {"event":"start","conversation_id":"demo","run_id":"demo"}\n\n',
    'data: {"event":"message","text":"Resposta simulada para revisão visual. Nenhum arquivo foi enviado ao Dify."}\n\n',
    'data: {"event":"done","status":"completed"}\n\n',
])).start()
app.config.update(CADU_FAMILY_CHAT_ENABLED=True, CADU_FAMILY_WRITES_ENABLED=True)

@app.before_request
def preview_identity():
    from flask import request
    if request.args.get('preview') == 'guest':
        session.clear()
    elif request.args.get('preview') == 'member':
        session.update(user_id=7, cliente_id=12, family_csrf='token')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8768, debug=False)
