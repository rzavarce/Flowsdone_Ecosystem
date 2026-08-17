"""CSPRNG-backed implementation of SecretGeneratorPort."""

from __future__ import annotations

import secrets


class RandomHexSecretGenerator:
    """Generates random hex secrets via `secrets.token_hex`.

    Pure-Python equivalent of `openssl rand -hex N`, backed by the
    OS's cryptographically secure random source — no subprocess call
    needed. Stateless and channel-agnostic, so any adapter that needs
    a webhook shared secret can depend on `SecretGeneratorPort`
    instead of rolling its own randomness.
    """

    def __init__(self, n_bytes: int = 32) -> None:
        """Build the generator.

        Args:
            n_bytes (int): Number of random bytes to generate; the
                resulting hex string is twice this length.
        """
        self._n_bytes = n_bytes

    def generate(self) -> str:
        """Generate a new random hex secret.

        Returns:
            str: A `2 * n_bytes`-character hex string.
        """
        return secrets.token_hex(self._n_bytes)
