import unittest
from unittest.mock import MagicMock

from aicentralv2.creative_media.studio_history import StudioCreationHistory


class StudioPersonalLibraryTest(unittest.TestCase):
    def test_personal_assets_are_scoped_to_client_and_owner(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [{
            "id": "45be8b92-5d95-4ccc-98f7-ff0356842072",
            "result": {
                "image_url": "https://cdn.example/piece.png",
                "title": "Peça pessoal",
                "aspect_ratio": "4:5",
            },
            "created_at": 1234,
        }]

        items = StudioCreationHistory(connection).personal_assets(17, 29)

        sql, params = cursor.execute.call_args.args
        self.assertIn("client_id=%s AND user_id=%s", sql)
        self.assertIn("project_id IS NULL", sql)
        self.assertIn("deleted_at IS NULL", sql)
        self.assertEqual(params, (17, 29, 100))
        self.assertEqual(items[0]["id"], "personal:45be8b92-5d95-4ccc-98f7-ff0356842072")
        self.assertTrue(items[0]["owner_only"])

    def test_invalid_personal_ids_never_reach_uuid_cast(self):
        connection = MagicMock()
        history = StudioCreationHistory(connection)

        with self.assertRaisesRegex(ValueError, "Escolha uma criação pessoal"):
            history.trash_personal_assets(17, 29, ["personal:not-a-uuid", ""])

        connection.cursor.assert_not_called()
        connection.commit.assert_not_called()

    def test_trash_is_scoped_to_owner_and_unassigned_generations(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.rowcount = 1
        generation_id = "45be8b92-5d95-4ccc-98f7-ff0356842072"

        removed = StudioCreationHistory(connection).trash_personal_assets(
            17, 29, [f"personal:{generation_id}"]
        )

        sql, params = cursor.execute.call_args.args
        self.assertIn("client_id=%s AND user_id=%s", sql)
        self.assertIn("project_id IS NULL", sql)
        self.assertIn("deleted_at IS NULL", sql)
        self.assertEqual(params, (17, 29, [generation_id]))
        self.assertEqual(removed, 1)
        connection.commit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
