"""Notarize — timestamp verification for fingerprints.

Stub implementation for Phase 4.2. Will support RFC 3161 or
OpenTimestamps for cryptographic proof of existence at a given time.
"""

from __future__ import annotations

import logging

from luna.fingerprint.generator import Fingerprint

log = logging.getLogger(__name__)


class Notarizer:
    """Timestamp notarization for fingerprint records.

    Currently a stub — logs the intent but does not perform
    actual notarization. Future implementation will use RFC 3161
    or OpenTimestamps.
    """

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled

    async def notarize(self, fingerprint: Fingerprint) -> str | None:
        """Submit a fingerprint for timestamp notarization.

        Args:
            fingerprint: The fingerprint to notarize.

        Returns:
            Notarization proof string, or None if not enabled/available.
        """
        if not self._enabled:
            log.debug("Notarization disabled — skipping")
            return None

        log.info(
            "Notarization stub: would notarize fingerprint %s for agent %s",
            fingerprint.composite[:16],
            fingerprint.agent_name,
        )
        return None

    async def verify(self, fingerprint: Fingerprint, proof: str) -> bool:
        """Verify a notarization proof.

        Args:
            fingerprint: The fingerprint to verify.
            proof: The notarization proof string.

        Returns:
            True if valid (currently always False — stub).
        """
        return False
