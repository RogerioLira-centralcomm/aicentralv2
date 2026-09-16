from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class WorkspaceDeployIntegrityTest(TestCase):
    def test_authenticated_sidebar_only_includes_versioned_partials(self):
        """The dashboard must render from a clean production checkout."""
        sidebar = (ROOT / "aicentralv2/templates/cadu_workspace/_app_sidebar.html").read_text()

        self.assertNotIn("cadu/_credit_meter.html", sidebar)
        self.assertNotIn("cadu/_user_avatar_image.html", sidebar)
