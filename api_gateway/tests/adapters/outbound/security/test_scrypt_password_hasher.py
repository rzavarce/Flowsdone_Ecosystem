"""Tests for ScryptPasswordHasher."""

from __future__ import annotations

from app.adapters.outbound.security.scrypt_password_hasher import ScryptPasswordHasher

# Costo bajo: los tests no necesitan los 32 MiB de producción.
_FAST = dict(n=2**10, r=8, p=1)


def test_hash_verifies_with_the_right_password_only():
    hasher = ScryptPasswordHasher(**_FAST)
    hashed = hasher.hash("correct-horse-battery")

    assert hasher.verify("correct-horse-battery", hashed) is True
    assert hasher.verify("wrong", hashed) is False


def test_hash_is_salted_so_equal_passwords_differ():
    hasher = ScryptPasswordHasher(**_FAST)
    assert hasher.hash("same") != hasher.hash("same")


def test_hash_never_contains_the_plaintext():
    assert "secret-pass" not in ScryptPasswordHasher(**_FAST).hash("secret-pass")


def test_hash_is_self_describing_and_parameters_travel_with_it():
    hashed = ScryptPasswordHasher(n=2**10, r=8, p=1).hash("x")
    assert hashed.startswith("scrypt$1024$8$1$")

    # Un hasher con OTROS parámetros por defecto verifica igual: los lee del hash.
    assert ScryptPasswordHasher(n=2**11, r=8, p=2).verify("x", hashed) is True


def test_supports_non_ascii_passwords():
    hasher = ScryptPasswordHasher(**_FAST)
    hashed = hasher.hash("contraseña-ñandú-🔐")
    assert hasher.verify("contraseña-ñandú-🔐", hashed) is True
    assert hasher.verify("contrasena-nandu", hashed) is False


def test_malformed_hashes_are_rejected_not_raised():
    hasher = ScryptPasswordHasher(**_FAST)
    for bad in ("", "nope", "scrypt$1$2$3", "bcrypt$1024$8$1$aa$bb", "scrypt$x$8$1$aa$bb", "scrypt$1024$8$1$!!$??"):
        assert hasher.verify("x", bad) is False


def test_default_parameters_meet_the_documented_cost():
    # OWASP: N=2^15, r=8, p=3. Guards against someone lowering it by accident.
    assert ScryptPasswordHasher().hash("x").startswith("scrypt$32768$8$3$")
