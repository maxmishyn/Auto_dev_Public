import os
import unittest

os.environ.setdefault('OPENAI_API_KEY', 'test')
os.environ.setdefault('SHARED_KEY', 'test')

from jobs.translate import build_translate_body


class TestBuildTranslateBody(unittest.TestCase):
    def test_html_is_preserved_and_messages_split(self):
        html = '<p>Hello <strong>World</strong></p>'
        body = build_translate_body(html, 'fr')
        expected_system = (
            'Translate the following HTML into fr. ' 
            'Preserve markup and return only translated HTML.'
        )
        self.assertEqual(
            body['input'],
            [
                {'role': 'system', 'content': expected_system},
                {'role': 'user', 'content': html},
            ],
        )
        # Ensure HTML markup is not altered
        self.assertEqual(body['input'][1]['content'], html)


if __name__ == '__main__':
    unittest.main()
