import unittest
import json
from utils import parse_response_output

class TestParseResponseOutput(unittest.TestCase):

    def test_chat_completions_format_correct(self):
        """
        Tests parsing of a standard, well-formed Chat Completions API response.
        """
        response = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-3.5-turbo-0125",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "This is the translated text."
                    },
                    "logprobs": None,
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 9,
                "completion_tokens": 12,
                "total_tokens": 21
            }
        }
        expected_output = "This is the translated text."
        self.assertEqual(parse_response_output(response), expected_output)

    def test_legacy_format_correct(self):
        """
        Tests parsing of the old, legacy format with an 'output' key.
        """
        response = {
            "id": "resp-123",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "This is the legacy text."
                        }
                    ]
                }
            ]
        }
        expected_output = "This is the legacy text."
        self.assertEqual(parse_response_output(response), expected_output)

    def test_empty_response(self):
        """
        Tests behavior with an empty dictionary.
        """
        self.assertEqual(parse_response_output({}), "")

    def test_no_choices_key(self):
        """
        Tests a response that is missing the 'choices' key.
        """
        response = {"id": "chatcmpl-123", "object": "chat.completion"}
        self.assertEqual(parse_response_output(response), "")

    def test_empty_choices_list(self):
        """
        Tests a response with an empty 'choices' list.
        """
        response = {"id": "chatcmpl-123", "choices": []}
        self.assertEqual(parse_response_output(response), "")

    def test_no_content_in_message(self):
        """
        Tests a choice item that is missing the 'content' key in its message.
        """
        response = {"choices": [{"message": {"role": "assistant"}}]}
        self.assertEqual(parse_response_output(response), "")

    def test_none_response(self):
        """
        Tests behavior when the input is None (although type hints suggest dict).
        """
        # This test case is commented out as the function expects a dict.
        # with self.assertRaises(TypeError):
        #     parse_response_output(None)
        # Depending on desired behavior, could return "" instead.
        # For now, we assume valid dict input.
        pass

if __name__ == '__main__':
    unittest.main()
