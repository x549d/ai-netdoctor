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
    def run_probe(self, status=401, error=None, proxy=None, dns_error=None, tcp_error=None, headers=None):
        with patch("ai_netdoctor.core._dns") as dns, patch("ai_netdoctor.core.socket.socket") as sock, patch("ai_netdoctor.core.httpx.Client") as client:
            dns.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
            dns.side_effect = dns_error
            sock.return_value.__enter__.return_value.connect.side_effect = tcp_error
            stream = client.return_value.__enter__.return_value.stream
            stream.side_effect = error
            response = httpx.Response(status, headers=headers, stream=httpx.ByteStream(b"private-body-marker"))
            stream.return_value.__enter__.return_value = response
            result = diagnose("openai", proxy, timeout=0.1)
            self.assertFalse(response.is_stream_consumed)
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
        proxy = "http://proxy-user:pwd-marker-123@127.0.0.1:7897"
        result, kwargs, dns_args = self.run_probe(proxy=proxy)
        self.assertEqual(dns_args[:2], ("127.0.0.1", 7897))
        self.assertEqual(kwargs["proxy"], proxy)
        self.assertEqual(result["probe_scope"], "proxy")
        serialized = json.dumps(result)
        self.assertNotIn("proxy-user", serialized)
        self.assertNotIn("pwd-marker-123", serialized)

    def test_timeout_is_explained_without_exception_text(self):
        result, _, _ = self.run_probe(error=httpx.ConnectTimeout("timeout-secret-marker"))
        self.assertFalse(result["reachable"])
        self.assertIn("timed out", result["steps"][-1]["message"])
        self.assertTrue(result["steps"][-1]["explanation"])
        self.assertTrue(result["steps"][-1]["recommended_actions"])
        self.assertNotIn("timeout-secret-marker", json.dumps(result))

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
        result, _, _ = self.run_probe(error=httpx.ProxyError("proxy-user:pwd-marker-456"))
        self.assertFalse(result["reachable"])
        self.assertIn("Proxy", result["steps"][-1]["message"])
        self.assertTrue(result["steps"][-1]["recommended_actions"])
        serialized = json.dumps(result)
        self.assertNotIn("proxy-user", serialized)
        self.assertNotIn("pwd-marker-456", serialized)

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
        self.assertIn("proxy requested authentication", result["steps"][-1]["explanation"].lower())

    def test_429_reports_safe_retry_after(self):
        for value, expected in (
            (" 120\t", "120"),
            ("0", "0"),
            ("Sun, 06 Nov 1994 08:49:37 GMT", "Sun, 06 Nov 1994 08:49:37 GMT"),
            ("Sunday, 06-Nov-94 08:49:37 GMT", "Sunday, 06-Nov-94 08:49:37 GMT"),
            ("Sun Nov  6 08:49:37 1994", "Sun Nov  6 08:49:37 1994"),
        ):
            with self.subTest(value=value):
                result, _, _ = self.run_probe(status=429, headers={"rEtRy-AfTeR": value})
                self.assertEqual(result["retry_after"], expected)
                self.assertTrue(result["reachable"])
                self.assertIn("shown under Retry-After", result["recommended_actions"][0])

    def test_429_omits_missing_or_unsafe_retry_after(self):
        for values in (
            [], [""], ["-1"], ["1.5"], ["9" * 11], ["120, 240"], ["120", "240"],
            ["Sun, 99 Nov 1994 08:49:37 GMT"], ["Sun, 06 Nov 1994 08:49:37 GMT private-marker"],
            ["120\r\nprivate-marker"], ["private-marker"],
        ):
            with self.subTest(values=values):
                headers = [("Retry-After", value) for value in values]
                result, _, _ = self.run_probe(status=429, headers=headers)
                self.assertNotIn("retry_after", result)
                self.assertIn("No usable Retry-After", result["recommended_actions"][0])
                self.assertNotIn("private-marker", json.dumps(result))

    def test_retry_after_is_only_reported_for_429(self):
        result, _, _ = self.run_probe(status=503, headers={"Retry-After": "120"})
        self.assertNotIn("retry_after", result)

    def test_cli_429_outputs_retry_after_without_other_headers_or_body(self):
        headers = {
            "Retry-After": "120",
            "Set-Cookie": "session=private-cookie-marker",
            "Authorization": "Bearer private-token-marker",
            "X-Request-ID": "private-request-marker",
        }
        result, _, _ = self.run_probe(status=429, headers=headers)
        for as_json in (False, True):
            with self.subTest(as_json=as_json):
                args = ["check", "openai"]
                if as_json:
                    args.append("--json")
                output = io.StringIO()
                with patch("ai_netdoctor.cli.diagnose", return_value=result), redirect_stdout(output):
                    code = main(args)
                rendered = output.getvalue()
                self.assertEqual(code, 0)
                if as_json:
                    self.assertEqual(json.loads(rendered)["results"][0]["retry_after"], "120")
                else:
                    self.assertIn("Retry-After: 120", rendered)
                for secret in ("private-cookie-marker", "private-token-marker", "private-request-marker", "private-body-marker"):
                    self.assertNotIn(secret, rendered)

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
