import auth


def test_create_and_authenticate_user(monkeypatch, tmp_path):
    db_path = tmp_path / "auth.db"
    monkeypatch.setattr(auth, "AUTH_DB_PATH", str(db_path))

    auth.init_auth_db()
    auth.create_user("operator1", "SecurePass123!", "operator")

    user = auth.authenticate("operator1", "SecurePass123!")
    assert user["username"] == "operator1"
    assert user["role"] == "operator"
    assert auth.authenticate("operator1", "wrong-password") is None


def test_password_is_not_stored_plaintext(monkeypatch, tmp_path):
    db_path = tmp_path / "auth.db"
    monkeypatch.setattr(auth, "AUTH_DB_PATH", str(db_path))

    auth.create_user("admin", "SecurePass123!", "admin")

    import sqlite3
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT password_hash, salt FROM users WHERE username='admin'").fetchone()

    assert row[0] != "SecurePass123!"
    assert len(row[0]) == 64
    assert len(row[1]) == 32


def test_password_validation(monkeypatch, tmp_path):
    db_path = tmp_path / "auth.db"
    monkeypatch.setattr(auth, "AUTH_DB_PATH", str(db_path))

    try:
        auth.create_user("user", "short", "viewer")
    except ValueError as exc:
        assert "at least" in str(exc)
    else:
        raise AssertionError("Expected weak password to be rejected")
