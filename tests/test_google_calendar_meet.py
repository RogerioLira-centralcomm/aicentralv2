import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from flask import Flask

from aicentralv2.services import google_calendar


ROOT = Path(__file__).resolve().parents[1]


class GoogleCalendarServiceTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            GOOGLE_OAUTH_CLIENT_ID="client-id",
            GOOGLE_OAUTH_CLIENT_SECRET="client-secret",
            GOOGLE_OAUTH_REDIRECT_URI="https://centralx.example/perfil/google/callback",
            GOOGLE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(),
            GOOGLE_CALENDAR_TIMEOUT=5,
        )
        self.context = self.app.app_context()
        self.context.push()

    def tearDown(self):
        self.context.pop()

    def test_authorization_url_uses_state_offline_and_minimum_scopes(self):
        url = google_calendar.authorization_url("state-seguro")
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["state"], ["state-seguro"])
        self.assertEqual(query["access_type"], ["offline"])
        self.assertIn("calendar.events", query["scope"][0])
        self.assertNotIn("calendar.readonly", query["scope"][0])

    def test_refresh_token_is_encrypted_at_rest(self):
        encrypted = google_calendar.encrypt_refresh_token("refresh-secret")
        self.assertNotIn("refresh-secret", encrypted)
        self.assertEqual(
            google_calendar.decrypt_refresh_token(encrypted), "refresh-secret"
        )

    def test_event_payload_has_idempotent_meet_and_safe_attendees(self):
        meeting = {
            "activity_id": "42",
            "starts_at": "2026-09-15T14:00:00-03:00",
            "ends_at": "2026-09-15T15:00:00-03:00",
            "timezone": "America/Sao_Paulo",
            "attendees": [{"name": "Cliente", "email": "cliente@example.com"}],
        }
        first = google_calendar.build_event_payload(
            {"titulo": "Planejamento", "descricao": "Pauta"}, meeting, True
        )
        second = google_calendar.build_event_payload(
            {"titulo": "Planejamento", "descricao": "Pauta"}, meeting, True
        )
        self.assertEqual(
            first["conferenceData"]["createRequest"]["requestId"],
            second["conferenceData"]["createRequest"]["requestId"],
        )
        self.assertEqual(first["attendees"][0]["email"], "cliente@example.com")
        self.assertNotIn("sendUpdates", first)

    def test_sync_uses_calendar_query_to_send_invites(self):
        response = MagicMock(ok=True)
        response.json.return_value = {
            "id": "event-1",
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
        }
        with patch.object(google_calendar, "_access_token", return_value="access"), patch.object(
            google_calendar.requests, "post", return_value=response
        ) as post:
            result = google_calendar.sync_event(
                {"titulo": "Reunião", "descricao": "Pauta"},
                {
                    "activity_id": "9",
                    "starts_at": "2026-09-15T14:00:00-03:00",
                    "ends_at": "2026-09-15T14:30:00-03:00",
                    "timezone": "America/Sao_Paulo",
                    "attendees": [],
                },
                "encrypted",
            )
        self.assertEqual(result["event_id"], "event-1")
        self.assertEqual(post.call_args.kwargs["params"]["sendUpdates"], "all")
        self.assertEqual(post.call_args.kwargs["params"]["conferenceDataVersion"], 1)


class GoogleCalendarSchemaContractTest(unittest.TestCase):
    def test_migration_and_deploy_cover_google_tables(self):
        migration = (ROOT / "migrations/add_google_calendar_meet.sql").read_text()
        deploy = (ROOT / "deploy.sh").read_text()
        for table in (
            "user_google_connections",
            "crm_activity_meetings",
            "crm_activity_meeting_attendees",
        ):
            self.assertIn(table, migration)
        self.assertIn("encrypted_refresh_token", migration)
        self.assertIn("run_add_google_calendar_meet.py", deploy)

    def test_oauth_callback_validates_state_and_profile_hides_token(self):
        routes = (ROOT / "aicentralv2/routes.py").read_text()
        template = (ROOT / "aicentralv2/templates/base_erp.html").read_text()
        self.assertIn("hmac.compare_digest(expected_state, received_state)", routes)
        self.assertIn("encrypt_refresh_token", routes)
        self.assertNotIn("encrypted_refresh_token", template)
        self.assertIn("Google Calendar e Meet", template)


if __name__ == "__main__":
    unittest.main()
