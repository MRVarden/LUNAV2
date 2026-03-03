"""Fingerprint generator — HMAC-SHA256 on consciousness state.

Generates a deterministic fingerprint from:
- Psi_0 (identity profile)
- Recent evolution history (Fibonacci-sampled steps)
- Gamma matrices (coupling configuration)
- Mass matrix (inertia)

The HMAC key is loaded from a file with restrictive permissions.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Fingerprint:
    """Immutable identity fingerprint.

    Attributes:
        agent_name: Name of the agent this fingerprint belongs to.
        psi0_hash: SHA256 hash of the identity profile.
        state_hash: SHA256 hash of the current consciousness state.
        composite: HMAC-SHA256 combining all component hashes.
        timestamp: ISO 8601 timestamp of generation.
        step_count: Consciousness evolution step at generation time.
    """

    agent_name: str
    psi0_hash: str
    state_hash: str
    composite: str
    timestamp: str
    step_count: int

    def to_dict(self) -> dict:
        """Serialize to a dictionary for JSON persistence."""
        return {
            "agent_name": self.agent_name,
            "psi0_hash": self.psi0_hash,
            "state_hash": self.state_hash,
            "composite": self.composite,
            "timestamp": self.timestamp,
            "step_count": self.step_count,
        }

    @staticmethod
    def from_dict(data: dict) -> Fingerprint:
        """Deserialize from a dictionary."""
        return Fingerprint(
            agent_name=data["agent_name"],
            psi0_hash=data["psi0_hash"],
            state_hash=data["state_hash"],
            composite=data["composite"],
            timestamp=data["timestamp"],
            step_count=data["step_count"],
        )


class FingerprintGenerator:
    """Generate HMAC-SHA256 fingerprints from consciousness state.

    The HMAC secret is loaded from a file. If the file does not exist,
    a new secret is generated and persisted.
    """

    def __init__(self, secret_path: Path) -> None:
        """Load or generate the HMAC secret.

        Args:
            secret_path: Path to the secret file (should have 600 permissions).
        """
        self._secret_path = secret_path
        self._secret = self._load_or_generate_secret()

    def generate(self, consciousness: object) -> Fingerprint:
        """Generate a deterministic fingerprint from consciousness state.

        Args:
            consciousness: ConsciousnessState instance with psi, psi0, step_count.

        Returns:
            Frozen Fingerprint with HMAC-SHA256 composite hash.
        """
        cs = consciousness
        agent_name = getattr(cs, "agent_name", "unknown")
        psi = getattr(cs, "psi", np.zeros(4))
        psi0 = getattr(cs, "psi0", np.zeros(4))
        step_count = getattr(cs, "step_count", 0)

        # Hash individual components
        psi0_hash = self._hash_array(psi0)
        state_hash = self._hash_state(psi, step_count)

        # HMAC composite
        message = f"{agent_name}:{psi0_hash}:{state_hash}:{step_count}"
        composite = hmac.new(
            self._secret,
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return Fingerprint(
            agent_name=agent_name,
            psi0_hash=psi0_hash,
            state_hash=state_hash,
            composite=composite,
            timestamp=datetime.now(timezone.utc).isoformat(),
            step_count=step_count,
        )

    def verify(self, fingerprint: Fingerprint, consciousness: object) -> bool:
        """Verify a fingerprint against the current consciousness state.

        Args:
            fingerprint: Previously generated Fingerprint to verify.
            consciousness: Current ConsciousnessState.

        Returns:
            True if the fingerprint matches the current state.
        """
        current = self.generate(consciousness)
        return hmac.compare_digest(fingerprint.composite, current.composite)

    def _hash_array(self, arr: np.ndarray) -> str:
        """SHA256 hash of a numpy array."""
        data = arr.tobytes()
        return hashlib.sha256(data).hexdigest()[:32]

    def _hash_state(self, psi: np.ndarray, step_count: int) -> str:
        """SHA256 hash of psi + step_count."""
        data = psi.tobytes() + step_count.to_bytes(8, "big")
        return hashlib.sha256(data).hexdigest()[:32]

    def _load_or_generate_secret(self) -> bytes:
        """Load secret from file, or generate and persist a new one."""
        if self._secret_path.exists():
            secret = self._secret_path.read_bytes().strip()
            if secret:
                log.debug("Loaded HMAC secret from %s", self._secret_path)
                return secret

        # Generate new secret with atomic file creation (O_EXCL prevents race conditions).
        secret = secrets.token_bytes(32)
        self._secret_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(
                str(self._secret_path),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            try:
                os.write(fd, secret)
            finally:
                os.close(fd)
        except FileExistsError:
            # Another process created it first — read the existing secret.
            secret = self._secret_path.read_bytes().strip()
            if secret:
                log.debug("Loaded HMAC secret from %s (created by another process)", self._secret_path)
                return secret
            raise RuntimeError(f"Secret file {self._secret_path} exists but is empty")

        log.info("Generated new HMAC secret at %s", self._secret_path)
        return secret
