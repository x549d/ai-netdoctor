import io
import json
import socket
import ssl
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import httpx

from ai_netdoctor.cli import main
from ai_netdoctor.core import diagnose, parse_proxy


class DiagnosticTests(unittest.TestCase):
    def run_probe(self, status=401, error=None, proxy=None, dns_error=None, tcp_error=None):
        with patch("ai_netdoctor.core._dns") as dns, patch("ai_netdoctor.core.socket.socket") as sock, patch("ai_netdoctor.core.httpx.Client") as client:
            dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
            dns.side_effect = dns_error
            sock.return_value.__enter__.return_value.connect.side_effect = tcp_error
            stream = client.return_value.__enter__.return_value.stream
            stream.side_effect = error
            stream.return_value.__enter__.return_value.status_code = status
            result = diagnose("openai", proxy, timeout=0.1)
            kwargs = client.call_args.kwargs
            dns_args = dns.call_args.args
        return result, kwargs, dns_args

    def test_401_is_http_reachable_without_credentials(self):
        result, kwargs, _ = self.run_probe()
        self.assertTrue(result["reachable"])
        self.assertEqual(result["http_status"], 401)
        self.assertFalse(kwargs["trust_env"])
        self.assertFalse(kwargs["follow_redirects"])
        self.assertIsNone(kwargs["proxy"])

    def test_proxy_scope_and_credentials_redaction(self):
        proxy = "http://alice:secret@127.0.0.1:7897"
        result, kwargs, dns_args = self.run_probe(proxy=proxy)
        self.assertEqual(dns_args[:2], ("127.0.0.1", 7897))
        self.assertEqual(kwargs["proxy"], proxy)
        self.assertEqual(result["probe_scope"], "proxy")
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("alice", json.dumps(result))

    def test_timeout_is_explained_without_exception_text(self):
        result, _, _ = self.run_probe(error=httpx.ConnectTimeout("secret"))
        self.assertFalse(result["reachable"])
        self.assertIn("timed out", result["steps"][-1]["message"])
        self.assertTrue(result["steps"][-1]["explanation"])
        self.assertTrue(result["steps"][-1]["recommended_actions"])
        self.assertNotIn("secret", json.dumps(result))

    def test_dns_failure_does_not_override_https_response(self):
        result, _, _ = self.run_probe(dns_error=socket.gaierror("unavailable"))
        self.assertFalse(result["steps"][0]["ok"])
        self.assertFalse(result["steps"][1]["ok"])
        self.assertTrue(result["reachable"])
        self.assertTrue(result["steps"][0]["explanation"])
        self.assertTrue(result["steps"][0]["recommended_actions"])

    def test_tcp_failure_is_reported_independently(self):
        result, _, _ = self.run_probe(tcp_error=ConnectionRefusedError())
        self.assertFalse(result["steps"][1]["ok"])
        self.assertTrue(result["reachable"])
        self.assertTrue(result["steps"][1]["explanation"])
        self.assertTrue(result["steps"][1]["recommended_actions"])

    def test_proxy_error_does_not_leak_credentials(self):
        result, _, _ = self.run_probe(error=httpx.ProxyError("alice:secret"))
        self.assertFalse(result["reachable"])
        self.assertIn("Proxy", result["steps"][-1]["message"])
        self.assertTrue(result["steps"][-1]["recommended_actions"])
        self.assertNotIn("secret", json.dumps(result))

    def test_tls_failure_is_classified(self):
        error = httpx.ConnectError("certificate verify failed")
        error.__cause__ = ssl.SSLCertVerificationError("untrusted")
        result, _, _ = self.run_probe(error=error)
        self.assertFalse(result["reachable"])
        self.assertIn("TLS", result["steps"][-1]["message"])
        self.assertTrue(result["steps"][-1]["recommended_actions"])
        self.assertTrue(any("Do not disable" in item for item in result["steps"][-1]["recommended_actions"]))

    def test_status_codes_are_distinct_from_api_success(self):
        for status in (200, 302, 400, 401, 403, 404, 429, 500):
            with self.subTest(status=status):
                result, _, _ = self.run_probe(status=status)
                self.assertTrue(result["reachable"])
                self.assertEqual(result["http_status"], status)
                self.assertTrue(result["steps"][-1]["explanation"])
                self.assertTrue(result["steps"][-1]["recommended_actions"])
        result, _, _ = self.run_probe(status=407)
        self.assertFalse(result["reachable"])
        self.assertIn("Proxy authentication", result["steps"][-1]["explanation"])

    def test_each_step_has_structured_guidance_fields(self):
        result, _, _ = self.run_probe(status=401)
        for step in result["steps"]:
            self.assertIn("explanation", step)
            self.assertIn("possible_causes", step)
            self.assertIn("recommended_actions", step)
        self.assertTrue(result["recommended_actions"])

    def test_proxy_validation(self):
        for value in ("127.0.0.1:7897", "socks5://localhost:1080", "http://", "http://host:0", "http://host:99999", "http://host/path", "http://host?token=secret"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_proxy(value)
        self.assertEqual(parse_proxy("http://[::1]:7897")[0], ("::1", 7897))

    def test_json_output_and_all_exit_code(self):
        output = io.StringIO()
        with patch("ai_netdoctor.cli.diagnose", side_effect=[{"reachable": True}, {"reachable": False}, {"reachable": True}]) as probe, redirect_stdout(output):
            code = main(["check", "--all", "--json"])
        self.assertEqual(code, 1)
        self.assertEqual(len(json.loads(output.getvalue())["results"]), 3)
        self.assertEqual([call.args[0] for call in probe.call_args_list], ["openai", "claude", "gemini"])

    def test_cli_text_includes_explanations_and_actions(self):
        report = {
            "target": "OpenAI API", "proxy": None, "probe_scope": "target",
            "probe_host": "api.openai.com", "probe_port": 443,
            "steps": [{
                "stage": "https", "ok": True, "message": "HTTP 401: response received.",
                "elapsed_ms": 1.0, "explanation": "Authentication is required.",
                "possible_causes": ["No API key was sent."],
                "recommended_actions": ["Check the API key in your application."]
            }],
            "result": "HTTP endpoint responded; API access is not verified.",
            "reachable": True
        }
        output = io.StringIO()
        with patch("ai_netdoctor.cli.diagnose", return_value=report), redirect_stdout(output):
            code = main(["check", "openai"])
        self.assertEqual(code, 0)
        self.assertIn("Explanation: Authentication is required.", output.getvalue())
        self.assertIn("Suggested action 1: Check the API key", output.getvalue())

    def test_cli_rejects_bad_arguments_before_network(self):
        for args in (["check"], ["check", "openai", "--all"], ["check", "openai", "--timeout", "nan"], ["check", "openai", "--timeout", "0"], ["check", "openai", "--proxy", "bad"]):
            with self.subTest(args=args), patch("ai_netdoctor.cli.diagnose") as probe, redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main(args)
            self.assertEqual(caught.exception.code, 2)
            probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
