"""Read saved PHP results without executing tools or exposing their inputs."""
import json
import re

from .legacy_files import project_files, safe_url

SMART_DOC = re.compile(r'<!--SMART_DOC:([\s\S]*?)-->', re.IGNORECASE)
MAX_CONTENT = 1_000_000


def saved_images(value, legacy_base=None):
    if isinstance(value, str):
        if len(value) > MAX_CONTENT:
            return []
        try:
            value = json.loads(value)
        except ValueError:
            return []
    if not isinstance(value, list):
        return []
    images = []
    for call in value[:100]:
        if not isinstance(call, dict) or call.get('tool') != 'image_generate':
            continue
        result = call.get('result')
        if not isinstance(result, dict) or result.get('success') is False:
            continue
        if isinstance(result.get('data'), dict):
            result = result['data']
        url = safe_url(result.get('image_url'), legacy_base) or safe_url(result.get('url'), legacy_base)
        if url:
            images.append({'name': 'Criativo gerado', 'url': url})
    return images


def readable_documents(content):
    if not isinstance(content, str) or len(content) > MAX_CONTENT:
        return content

    def replace(match):
        try:
            doc = json.loads(match.group(1))
        except ValueError:
            return match.group(0)  # Preserve unrecognized data instead of dropping it.
        if not isinstance(doc, dict) or not isinstance(doc.get('conteudo'), str) or not doc['conteudo'].strip():
            return match.group(0)
        title = doc.get('titulo')
        title = title[:250] if isinstance(title, str) and title.strip() else 'Documento'
        # The shared renderer escapes HTML; this is text, not executable markup.
        return '\n\n' + title + '\n\n' + doc['conteudo'] + '\n\n'

    return SMART_DOC.sub(replace, content)


def project_message(message, legacy_base=None):
    files = project_files(message.get('files'), legacy_base)
    content = message.get('content')
    if message.get('role') == 'assistant':
        urls = {item['url'] for item in files if item['url']}
        for image in saved_images(message.get('tool_calls'), legacy_base):
            if image['url'] not in urls:
                files.append(image)
                urls.add(image['url'])
        content = readable_documents(content)
    return {**{key: value for key, value in message.items() if key != 'tool_calls'},
            'content': content, 'files': files}
