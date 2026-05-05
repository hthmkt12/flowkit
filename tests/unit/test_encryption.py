"""Tests for encryption/decryption in agent.db.crud."""
import json
import pytest


class TestKeyDerivation:
    """Test _derive_fernet_key produces valid Fernet keys."""

    def test_derives_valid_fernet_key(self):
        from agent.db.crud import _derive_fernet_key
        from cryptography.fernet import Fernet
        key = _derive_fernet_key("my-secret-key-material")
        # Should not raise
        f = Fernet(key)
        # Round-trip test
        data = b"hello world"
        assert f.decrypt(f.encrypt(data)) == data

    def test_different_seeds_different_keys(self):
        from agent.db.crud import _derive_fernet_key
        k1 = _derive_fernet_key("seed-one")
        k2 = _derive_fernet_key("seed-two")
        assert k1 != k2

    def test_same_seed_same_key(self):
        from agent.db.crud import _derive_fernet_key
        k1 = _derive_fernet_key("deterministic")
        k2 = _derive_fernet_key("deterministic")
        assert k1 == k2

    def test_empty_seed_uses_fallback(self):
        from agent.db.crud import _derive_fernet_key
        k_empty = _derive_fernet_key("")
        k_none = _derive_fernet_key(None)
        # Both should use the same fallback
        assert k_empty == k_none

    def test_key_is_32_bytes_base64(self):
        import base64
        from agent.db.crud import _derive_fernet_key
        key = _derive_fernet_key("test")
        raw = base64.urlsafe_b64decode(key)
        assert len(raw) == 32


class TestEncryptDecrypt:
    """Test encrypt/decrypt helpers."""

    def test_roundtrip_string(self):
        from agent.db.crud import _encrypt_if_needed, _decrypt_if_needed
        original = "my-secret-cookie-value"
        encrypted = _encrypt_if_needed("cookies_data", original)
        assert encrypted != original  # Must be encrypted
        decrypted = _decrypt_if_needed("cookies_data", encrypted)
        assert decrypted == original

    def test_roundtrip_dict(self):
        from agent.db.crud import _encrypt_if_needed, _decrypt_if_needed
        original = {"token": "abc123", "expires": 12345}
        encrypted = _encrypt_if_needed("session_data", original)
        decrypted = _decrypt_if_needed("session_data", encrypted)
        # Dict is serialized to JSON string before encryption
        assert json.loads(decrypted) == original

    def test_roundtrip_list(self):
        from agent.db.crud import _encrypt_if_needed, _decrypt_if_needed
        original = [{"name": "c_user", "value": "123"}]
        encrypted = _encrypt_if_needed("cookies_data", original)
        decrypted = _decrypt_if_needed("cookies_data", encrypted)
        assert json.loads(decrypted) == original

    def test_non_sensitive_field_passthrough(self):
        from agent.db.crud import _encrypt_if_needed, _decrypt_if_needed
        original = "plain-text-name"
        assert _encrypt_if_needed("name", original) == original
        assert _decrypt_if_needed("name", original) == original

    def test_none_passthrough(self):
        from agent.db.crud import _encrypt_if_needed, _decrypt_if_needed
        assert _encrypt_if_needed("cookies_data", None) is None
        assert _decrypt_if_needed("cookies_data", None) is None

    def test_backward_compat_plaintext_read(self):
        """If DB has old unencrypted data, decrypt should return it as-is."""
        from agent.db.crud import _decrypt_if_needed
        plaintext = "old-plaintext-cookie-data"
        # Should not crash — returns plaintext when decryption fails
        result = _decrypt_if_needed("cookies_data", plaintext)
        assert result == plaintext


class TestDecryptAccountRow:
    """Test _decrypt_account_row helper."""

    def test_none_input(self):
        from agent.db.crud import _decrypt_account_row
        assert _decrypt_account_row(None) is None

    def test_empty_dict(self):
        from agent.db.crud import _decrypt_account_row
        assert _decrypt_account_row({}) == {}

    def test_decrypts_sensitive_fields(self):
        from agent.db.crud import (
            _encrypt_if_needed, _decrypt_account_row,
        )
        enc_cookies = _encrypt_if_needed("cookies_data", "secret-cookies")
        enc_session = _encrypt_if_needed("session_data", "secret-session")
        row = {
            "id": "abc",
            "name": "Test",
            "cookies_data": enc_cookies,
            "session_data": enc_session,
        }
        result = _decrypt_account_row(row)
        assert result["cookies_data"] == "secret-cookies"
        assert result["session_data"] == "secret-session"
        assert result["name"] == "Test"  # Unchanged
