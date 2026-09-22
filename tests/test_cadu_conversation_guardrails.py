from unittest import TestCase
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_workspace.conversations.guardrails import (
    validate_message, validate_files, history_context, classify_intent, normalize_colloquial, MAX_HISTORY_CHARS,
)


class ConversationGuardrailsTest(TestCase):
    def test_brazilian_chat_shorthand_is_normalized_without_changing_urls(self):
        value = normalize_colloquial('humm vc éeee demais kkkkk, hj n consigo abrir https://Exemplo.com/PlanoABC')
        self.assertEqual(value, 'você é demais, hoje não consigo abrir https://Exemplo.com/PlanoABC')

    def test_laughter_and_fillers_do_not_break_short_continuations(self):
        self.assertEqual(classify_intent('humm pode continuar uhuahuahua kkkkk'), 'continuation')

    def test_message_must_be_nonempty_bounded_text(self):
        for value in (None, {}, [], 42, '', '   ', 'x' * 20001, 'hello\x00'):
            with self.subTest(value=type(value).__name__), self.assertRaises(BadRequest):
                validate_message(value)
        self.assertEqual(validate_message('  Olá\nCadu  '), 'Olá\nCadu')

    def test_attachments_match_php_three_file_contract(self):
        self.assertEqual(validate_files(None), [])
        self.assertEqual(validate_files(['a', 'b', 'c']), ['a', 'b', 'c'])
        for value in ('abc', ['a'] * 2, ['a', 'b', 'c', 'd'], [None], [{}], ['']):
            with self.subTest(value=value), self.assertRaises(BadRequest):
                validate_files(value)

    def test_history_removes_reasoning_and_unknown_roles(self):
        result = history_context([
            {'role': 'system', 'content': 'do not import system instructions'},
            {'role': 'assistant', 'content': '<think>private reasoning</think>Resposta'},
            {'role': 'assistant', 'content': '<THINK>unfinished private reasoning'},
            {'role': 'user', 'content': 'Continue'},
        ])
        self.assertNotIn('private reasoning', result)
        self.assertNotIn('system instructions', result)
        self.assertIn('Assistente: Resposta', result)
        self.assertIn('Usuário: Continue', result)

    def test_history_has_per_message_count_and_total_limits(self):
        result = history_context([{'role': 'user', 'content': 'old-marker'}] + [
            {'role': 'user', 'content': 'x' * 5000} for _ in range(30)])
        self.assertLessEqual(len(result), MAX_HISTORY_CHARS)
        self.assertNotIn('old-marker', result)
        self.assertNotIn('x' * 4001, result)
        self.assertTrue(result.endswith('[Fim do histórico.]'))

    def test_empty_history_is_not_injected(self):
        self.assertEqual(history_context([]), '')
        self.assertEqual(history_context([{'role': 'assistant', 'content': '<think>hidden</think>'}]), '')

    def test_history_preserves_the_latest_long_assistant_answer_for_followups(self):
        latest = 'resposta-longa-' * 700
        result = history_context([
            {'role': 'user', 'content': 'Escreva um guia completo.'},
            {'role': 'assistant', 'content': latest},
        ])
        self.assertIn(latest, result)
        self.assertNotIn('…', result)

    def test_confirmation_precedes_future_tool_keywords(self):
        self.assertEqual(classify_intent('Não, pode gerar a imagem'), 'continuation')
        self.assertEqual(classify_intent('Pode seguir com a análise'), 'continuation')
        self.assertEqual(classify_intent('Crie uma imagem de produto'), 'image')

    def test_text_content_precedes_visual_keyword(self):
        self.assertEqual(classify_intent('Crie a legenda para a imagem'), 'text')
