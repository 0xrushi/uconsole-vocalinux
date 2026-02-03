"""Tests for Gemini client."""

import unittest


from vocalinux.llm.gemini_client import GeminiClient, GeminiRequest


class _FakeResp:
    def __init__(self, *, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


class _FakeSession:
    def __init__(self, resp):
        self._resp = resp
        self.last_url = None
        self.last_json = None
        self.last_timeout = None

    def post(self, url, json=None, timeout=None):
        self.last_url = url
        self.last_json = json
        self.last_timeout = timeout
        return self._resp


class TestGeminiClient(unittest.TestCase):
    def test_generate_text_success(self):
        resp = _FakeResp(
            json_data={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "hello"}]},
                    }
                ]
            }
        )
        session = _FakeSession(resp)
        client = GeminiClient(session=session)
        out = client.generate_text(
            GeminiRequest(
                model="gemini-3-flash-preview",
                api_key="k",
                prompt="p",
                timeout_seconds=3,
            )
        )
        self.assertEqual(out, "hello")
        self.assertIn("gemini-3-flash-preview", session.last_url)
        self.assertEqual(session.last_timeout, 3)
        self.assertEqual(session.last_json["contents"][0]["parts"][0]["text"], "p")

    def test_generate_text_http_error(self):
        resp = _FakeResp(status_code=400, json_data={"error": "bad"}, text="bad")
        client = GeminiClient(session=_FakeSession(resp))
        with self.assertRaises(RuntimeError):
            client.generate_text(GeminiRequest(model="m", api_key="k", prompt="p"))

    def test_generate_text_bad_shape(self):
        resp = _FakeResp(json_data={"candidates": []})
        client = GeminiClient(session=_FakeSession(resp))
        with self.assertRaises(RuntimeError):
            client.generate_text(GeminiRequest(model="m", api_key="k", prompt="p"))
