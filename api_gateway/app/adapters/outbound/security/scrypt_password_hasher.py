"""scrypt implementation of PasswordHasherPort (standard library only)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_PREFIX = "scrypt"
# OWASP-recommended scrypt configuration: N=2^15 (32 MiB), r=8, p=3.
_DEFAULT_N = 2**15
_DEFAULT_R = 8
_DEFAULT_P = 3
_DKLEN = 32
_SALT_BYTES = 16


def _b64(data: bytes) -> str:
    """URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    """Inverse of `_b64`."""
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class ScryptPasswordHasher:
    """Hashes passwords with scrypt, storing the parameters in the hash.

    Format: `scrypt$<N>$<r>$<p>$<salt>$<digest>`. Because the parameters
    travel with each hash, they can be raised later without invalidating
    existing passwords. Uses only `hashlib`/`hmac`, so it adds no
    dependency. Each call is CPU/memory heavy (~50-100 ms, 32 MiB):
    callers on an event loop must run it in a worker thread.
    """

    def __init__(self, *, n: int = _DEFAULT_N, r: int = _DEFAULT_R, p: int = _DEFAULT_P) -> None:
        """Build the hasher.

        Args:
            n (int): CPU/memory cost (power of two). Tests lower it.
            r (int): Block size.
            p (int): Parallelization.
        """
        self._n, self._r, self._p = n, r, p

    @staticmethod
    def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
        """Run scrypt with a memory cap sized for the given parameters."""
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=_DKLEN,
            maxmem=128 * n * r * 2,
        )

    def hash(self, password: str) -> str:
        """Hash a password with a fresh random salt.

        Args:
            password (str): The plaintext password.

        Returns:
            str: A self-describing hash, safe to store.
        """
        salt = secrets.token_bytes(_SALT_BYTES)
        digest = self._derive(password, salt, self._n, self._r, self._p)
        return f"{_PREFIX}${self._n}${self._r}${self._p}${_b64(salt)}${_b64(digest)}"

    def verify(self, password: str, password_hash: str) -> bool:
        """Check a password against a stored hash in constant time.

        Args:
            password (str): The plaintext password to check.
            password_hash (str): A hash previously returned by `hash`.

        Returns:
            bool: True if it matches; False for a mismatch or a
            malformed/unsupported hash.
        """
        try:
            prefix, n, r, p, salt, digest = password_hash.split("$")
            if prefix != _PREFIX:
                return False
            expected = _unb64(digest)
            actual = self._derive(password, _unb64(salt), int(n), int(r), int(p))
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(actual, expected)
