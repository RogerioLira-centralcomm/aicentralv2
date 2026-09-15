"""Project Dify events onto the customer chat contract, never raw workflow data.

Legacy reference: DifyStream.js. Deliberately do not promote agent_thought to
an answer or disclose reasoning, tool inputs/observations, node titles or files.
Tool execution/confirmation and authorized result cards are separate contracts.
"""


def object_value(value):
    return value if isinstance(value, dict) else {}


class ProviderEvents:
    def __init__(self):
        self.answer = ''
        self.usage = {}
        self.completed = False
        self.failed = False
        self.last_progress = None

    def feed(self, event):
        if not isinstance(event, dict) or self.failed:
            return []
        kind = event.get('event')
        data = object_value(event.get('data'))
        output = []
        if kind == 'error' or (kind == 'workflow_finished' and data.get('status') in ('failed', 'stopped', 'partial-succeeded')):
            self.failed = True
            self.completed = False
            raise ValueError('Provider generation failed')
        if self.completed:
            return []
        chunk = None
        replacement = None
        if kind in ('message', 'agent_message'):
            chunk = event.get('answer')
        elif kind == 'text_chunk':
            chunk = data.get('text')
        elif kind == 'message_replace':
            replacement = event.get('answer')
        elif kind == 'workflow_finished':
            # Workflow outputs are not terminal confirmation for the chat API.
            replacement = object_value(data.get('outputs')).get('answer')
        elif kind == 'message_end':
            replacement = event.get('answer')
            self.usage = object_value(object_value(event.get('metadata')).get('usage'))
            self.completed = True
        if isinstance(chunk, str) and chunk:
            self.answer += chunk
            output.append({'event': 'message', 'text': chunk})
            self.last_progress = None
        if isinstance(replacement, str) and (replacement or kind == 'message_replace') and replacement != self.answer:
            self.answer = replacement
            output.append({'event': 'replace', 'text': replacement})
        # Fixed customer-facing states; do not pass arbitrary provider payloads.
        progress = {
            'workflow_started': ('preparing', 'Preparando a resposta…'),
            'node_started': ('processing', 'Processando a solicitação…'),
            'node_finished': ('processing', 'Processando a solicitação…'),
            'tool_call': ('tool', 'Processando um recurso da conversa…'),
            'agent_thought': ('processing', 'Processando a solicitação…'),
            'thinking': ('processing', 'Processando a solicitação…'),
            'message_thinking': ('processing', 'Processando a solicitação…'),
        }.get(kind)
        if progress and progress != self.last_progress:
            self.last_progress = progress
            output.append({'event': 'progress', 'stage': progress[0], 'message': progress[1]})
        return output
