from pathlib import Path
import os
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class WorkspaceDeployIntegrityTest(TestCase):
    def test_deploy_script_is_executable(self):
        """Production operators can invoke the documented ./deploy.sh command."""
        self.assertTrue(os.access(ROOT / "deploy.sh", os.X_OK))

    def test_authenticated_shell_partials_are_present_in_the_checkout(self):
        """The dashboard must render from a clean production checkout."""
        templates = ROOT / "aicentralv2/templates"
        studio_context_bar = (templates / "cadu_studio/_context_bar.html").read_text()

        for partial in ("cadu/_credit_meter.html", "cadu/_user_avatar_image.html"):
            self.assertIn(partial, studio_context_bar)
            self.assertTrue((templates / partial).is_file(), partial)

    def test_deploy_restores_versioned_react_bundles_before_pull(self):
        """Generated Cadu bundles must not block the production merge."""
        deploy = (ROOT / "deploy.sh").read_text()

        for asset in (
            "aicentralv2/static/cadu_workspace/conversations/react/app.css",
            "aicentralv2/static/cadu_workspace/conversations/react/app.js",
        ):
            self.assertIn(f'restore_generated_file "{asset}"', deploy)
