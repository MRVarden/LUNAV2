"""Tests for SSRF protection in webhook URL validation.

Validates the P0 correction: _validate_webhook_url rejects private,
loopback, link-local, and non-HTTP URLs while accepting valid public
endpoints.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from luna.observability.alerting import _validate_webhook_url


# ---------------------------------------------------------------------------
# Private / internal IP ranges
# ---------------------------------------------------------------------------


class TestSSRFPrivateIPRejection:
    """_validate_webhook_url must reject URLs that resolve to private IPs."""

    def test_rejects_private_ip_10(self):
        """10.0.0.0/8 range is blocked (RFC 1918)."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("10.0.0.1", 80)),
            ]
            assert _validate_webhook_url("http://10.0.0.1/hook") is False

    def test_rejects_private_ip_172(self):
        """172.16.0.0/12 range is blocked (RFC 1918)."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("172.16.0.1", 80)),
            ]
            assert _validate_webhook_url("http://172.16.0.1/hook") is False

    def test_rejects_private_ip_192(self):
        """192.168.0.0/16 range is blocked (RFC 1918)."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("192.168.1.1", 80)),
            ]
            assert _validate_webhook_url("http://192.168.1.1/hook") is False

    def test_rejects_loopback(self):
        """127.0.0.0/8 (loopback) is blocked."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("127.0.0.1", 80)),
            ]
            assert _validate_webhook_url("http://127.0.0.1/hook") is False

    def test_rejects_metadata(self):
        """169.254.0.0/16 link-local (cloud metadata endpoint) is blocked."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("169.254.169.254", 80)),
            ]
            assert _validate_webhook_url("http://169.254.169.254/latest") is False


# ---------------------------------------------------------------------------
# Scheme validation
# ---------------------------------------------------------------------------


class TestSSRFSchemeValidation:
    """Only http and https schemes are allowed."""

    def test_rejects_non_http_scheme(self):
        """ftp:// scheme is rejected without DNS lookup."""
        assert _validate_webhook_url("ftp://evil.com") is False

    def test_rejects_file_scheme(self):
        """file:// scheme is rejected."""
        assert _validate_webhook_url("file:///etc/passwd") is False

    def test_rejects_empty_url(self):
        """Empty string is rejected (no scheme, no hostname)."""
        assert _validate_webhook_url("") is False


# ---------------------------------------------------------------------------
# Valid public URLs
# ---------------------------------------------------------------------------


class TestSSRFAcceptsPublicURLs:
    """Valid public URLs with safe resolved IPs should be accepted."""

    def test_accepts_valid_public_url(self):
        """A public HTTPS URL resolving to a non-private IP is accepted."""
        with patch("socket.getaddrinfo") as mock_dns:
            # Simulate DNS resolving to a public IP
            mock_dns.return_value = [
                (2, 1, 6, "", ("203.0.113.50", 443)),
            ]
            assert _validate_webhook_url("https://hooks.example.com/webhook") is True

    def test_accepts_http_public_url(self):
        """A public HTTP URL resolving to a non-private IP is accepted."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("198.51.100.10", 80)),
            ]
            assert _validate_webhook_url("http://hooks.example.com/webhook") is True

    def test_rejects_dns_failure(self):
        """URL whose hostname fails DNS resolution is rejected."""
        import socket

        with patch("socket.getaddrinfo", side_effect=socket.gaierror("DNS failure")):
            assert _validate_webhook_url("https://nonexistent.invalid/hook") is False
