from aicentralv2.cadu_workspace.conversations.working_memory import proposals


def test_extracts_only_actionable_project_sections_as_proposals():
    result = proposals('''## Riscos
- Aprovação do key visual ainda depende da direção.
## Próximos passos
1. Validar o pacote de formatos com criação.
## Texto livre
Talvez seja melhor fazer algo depois.''')
    assert result == [
        {'kind': 'risk', 'summary': 'Aprovação do key visual ainda depende da direção.'},
        {'kind': 'next_step', 'summary': 'Validar o pacote de formatos com criação.'},
    ]


def test_ignores_unstructured_or_uncertain_prose():
    assert proposals('''Acho que talvez seja bom fazer uma revisão.\n\nSem lista estruturada.''') == []
