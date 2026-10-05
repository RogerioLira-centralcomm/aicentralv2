from unittest.mock import patch

from aicentralv2 import creative_brand_analysis as analysis


class _Response:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def test_framework_stylesheets_and_default_colors_do_not_lead_the_brand_palette():
    pages = {
        "https://www.bdmg.mg.gov.br/": '<link rel="stylesheet" href="/css/bootstrap.min.css">'
                                       '<link rel="stylesheet" href="/css/site.css"><style>.x{color:#17A2B8}</style>',
        "https://www.bdmg.mg.gov.br/css/bootstrap.min.css": "#dc3545 " * 50,
        "https://www.bdmg.mg.gov.br/css/site.css": "#D22828 #D22828 #DC3545 #DC3545 #DC3545",
    }
    with patch.object(analysis.requests, "get", side_effect=lambda url, **_: _Response(pages[url])):
        colors = analysis._css_color_evidence("https://www.bdmg.mg.gov.br/")
    assert colors[0]["hex"] == "#D22828"
    assert {item["hex"] for item in colors if item.get("framework_default")} == {"#DC3545", "#17A2B8"}
    assert next(item for item in colors if item["hex"] == "#DC3545")["occurrences"] == 3  # bootstrap.min.css skipped
