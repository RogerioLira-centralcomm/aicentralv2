"""Office sources keep the structure that retrieval and citations depend on."""
from io import BytesIO
from zipfile import ZipFile

from openpyxl import Workbook
from werkzeug.datastructures import FileStorage

from aicentralv2.cadu_workspace import project_knowledge, project_sources

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'


def upload(name, data):
    return project_sources.validate_upload(FileStorage(stream=BytesIO(data), filename=name))


def package(files):
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def paragraph(text, style=''):
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
    return f'<w:p>{props}<w:r><w:t>{text}</w:t></w:r></w:p>'


def test_docx_keeps_paragraphs_headings_and_tables():
    body = (paragraph('Plano de mídia Q4', 'Title') + paragraph('Objetivo', 'Heading1')
            + paragraph('Gerar leads B2B.') + paragraph('Segundo parágrafo com detalhes.')
            + '<w:tbl><w:tr><w:tc>' + paragraph('Canal') + '</w:tc><w:tc>' + paragraph('Verba')
            + '</w:tc></w:tr><w:tr><w:tc>' + paragraph('Google Ads') + '</w:tc><w:tc>'
            + paragraph('R$ 30 mil') + '</w:tc></w:tr></w:tbl>')
    data = package({'word/document.xml': f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'})

    text = upload('plano.docx', data)['text']

    assert text.startswith('# Plano de mídia Q4\n\n## Objetivo\n\nGerar leads B2B.\n\nSegundo parágrafo')
    assert '| Canal | Verba |\n| Google Ads | R$ 30 mil |' in text
    assert [section for _value, section in project_knowledge.split(text)][-1] == 'Objetivo'


def test_xlsx_rows_are_labelled_by_header():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Mídia'
    sheet.append(['Canal', 'Verba', 'KPI'])
    sheet.append(['Google Ads', 30000, 'CPL'])
    sheet.append(['Meta Ads', 20000, None])
    buffer = BytesIO()
    workbook.save(buffer)

    source = upload('plano.xlsx', buffer.getvalue())

    assert '## Planilha: Mídia' in source['text']
    assert 'Canal: Google Ads; Verba: 30000; KPI: CPL' in source['text']
    assert 'Canal: Meta Ads; Verba: 20000' in source['text']
    assert source['classification']['category'] in {'media_plan', 'spreadsheet'}


def test_pptx_keeps_slide_order_and_notes():
    def slide(*texts):
        runs = ''.join(f'<a:p><a:r><a:t>{text}</a:t></a:r></a:p>' for text in texts)
        return f'<p:sld xmlns:p="urn:p" xmlns:a="{A}"><p:cSld><p:spTree><p:sp><p:txBody>{runs}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
    data = package({
        'ppt/presentation.xml': '<p:presentation xmlns:p="urn:p"/>',
        'ppt/slides/slide10.xml': slide('Próximos passos'),
        'ppt/slides/slide2.xml': slide('Estratégia', 'Foco em leads qualificados'),
        'ppt/notesSlides/notesSlide2.xml': slide('Reforçar o CPL alvo', '2'),
    })

    text = upload('apresentacao.pptx', data)['text']

    assert text.index('## Slide 2') < text.index('## Slide 10')
    assert 'Estratégia\nFoco em leads qualificados\n\nNotas: Reforçar o CPL alvo' in text


def test_repeated_passages_do_not_break_indexing(monkeypatch):
    monkeypatch.setattr(project_knowledge, '_embed', lambda texts: (
        [[0.0] * project_knowledge.EMBEDDING_DIMENSIONS for _ in texts], len(texts), 'test'))
    repeated = 'Cabeçalho confidencial da agência repetido em toda página.'
    records, _tokens, _model = project_knowledge.index(
        f'{repeated}\n\n' + 'Conteúdo único da página um. ' * 80 + f'\n\n{repeated}')
    hashes = [record.content_hash for record in records]
    assert len(hashes) == len(set(hashes))


def test_section_title_is_embedded_with_later_chunks_of_the_section(monkeypatch):
    embedded = []
    monkeypatch.setattr(project_knowledge, '_embed', lambda texts: (
        embedded.extend(texts) or [[0.0] * project_knowledge.EMBEDDING_DIMENSIONS for _ in texts], 1, 'test'))
    body = '\n\n'.join(f'Parágrafo {index} sobre a distribuição da verba de mídia paga. ' * 6 for index in range(12))
    records, _tokens, _model = project_knowledge.index(f'## Orçamento Q4\n\n{body}')
    assert len(records) > 1
    assert embedded[-1].startswith('Orçamento Q4\n\n')
    assert not records[-1].content.startswith('Orçamento Q4')
