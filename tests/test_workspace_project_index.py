import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from aicentralv2.cadu_workspace import project_index_jobs, project_index_service, project_resource_service


class WorkspaceProjectIndexTest(TestCase):
    def test_resource_id_matches_registry_namespace(self):
        self.assertEqual(
            project_index_service.project_resource_id(12, "ci:project-1", 8),
            project_resource_service.resource_id_for_source(12, "ci:project-1", "workspace", "file:8"),
        )

    def test_persisted_chunks_receive_resource_provenance(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"id": 8}
        chunk = SimpleNamespace(order=0, section="Briefing", content="Contexto indexado.",
                                content_hash="a" * 64, embedding=[0.1], tokens=4)

        source_id = project_index_service.persist_indexed_source(
            cursor, project_id="project-1", client_id=12, user_id=7,
            name="brief.md", mime="text/markdown", size=19,
            storage_path="workspace_project_sources/12/project-1/brief.md",
            source="workspace_upload", content="Contexto indexado.", chunks=[chunk],
            embedding_model="text-embedding-3-small", charged_tokens=4,
        )

        self.assertEqual(source_id, 8)
        chunk_sql = [call for call in cursor.execute.call_args_list if "INSERT INTO cadu_ci_chunks" in call.args[0]][0]
        self.assertIn("resource_id", chunk_sql.args[1][7])
        self.assertIn("arquivo_id", chunk_sql.args[1][7])

    def test_normalized_content_hash_is_not_overwritten_by_source_hash(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"id": 8}
        chunk = SimpleNamespace(order=0, section="", content="Texto normalizado.",
                                content_hash="b" * 64, embedding=[0.1], tokens=3)

        project_index_service.persist_indexed_source(
            cursor, project_id="project-1", client_id=12, user_id=7,
            name="brief.html", mime="text/html", size=20,
            storage_path="workspace_project_sources/12/project-1/brief.html",
            source="workspace_upload", content="Texto normalizado.", chunks=[chunk],
            embedding_model="text-embedding-3-small", charged_tokens=3,
            metadata={"sha256": "raw-upload-hash"},
        )

        source_sql = [call for call in cursor.execute.call_args_list
                      if "INSERT INTO cadu_ci_projeto_arquivos" in call.args[0]][0]
        metadata = json.loads(source_sql.args[1][-1])
        self.assertNotEqual(metadata["sha256"], "raw-upload-hash")
        self.assertEqual(metadata["source_sha256"], "raw-upload-hash")

    @patch("aicentralv2.cadu_workspace.project_index_jobs.get_db")
    def test_enqueue_updates_source_in_same_transaction(self, get_db):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            {"relation": "cadu_project_index_jobs"},
            {"id": "job-1"},
        ]
        get_db.return_value = connection

        result = project_index_jobs.enqueue(12, "project-1", 8, 7)

        self.assertEqual(result, "job-1")
        self.assertTrue(any("SET indexing_status='queued'" in call.args[0]
                            for call in cursor.execute.call_args_list))
        connection.commit.assert_called_once_with()

    @patch("aicentralv2.cadu_workspace.project_index_jobs.get_db")
    def test_enqueue_returns_existing_active_job_id(self, get_db):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            {"relation": "cadu_project_index_jobs"},
            None,
            {"id": "existing-job"},
        ]
        get_db.return_value = connection

        result = project_index_jobs.enqueue(12, "project-1", 8, 7)

        self.assertEqual(result, "existing-job")
        self.assertFalse(any("SET indexing_status='queued'" in call.args[0]
                             for call in cursor.execute.call_args_list))
