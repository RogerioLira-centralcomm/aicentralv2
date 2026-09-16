from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class WorkspaceDeployIntegrityTest(TestCase):
    def test_authenticated_shell_partials_are_present_in_the_checkout(self):
        """The dashboard must render from a clean production checkout."""
        templates = ROOT / "aicentralv2/templates"
        studio_context_bar = (templates / "cadu_studio/_context_bar.html").read_text()

        for partial in ("cadu/_credit_meter.html", "cadu/_user_avatar_image.html"):
            self.assertIn(partial, studio_context_bar)
            self.assertTrue((templates / partial).is_file(), partial)
