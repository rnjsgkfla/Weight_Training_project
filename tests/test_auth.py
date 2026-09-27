"""회원가입·로그인·탈퇴."""
from conftest import signup


def test_signup_then_me(client):
    headers = signup(client, email="Me@Example.com")
    res = client.get("/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] == "me@example.com"  # 소문자로 정규화


def test_duplicate_email_is_rejected(client):
    signup(client)
    res = client.post("/auth/signup", json={"email": "ME@example.com", "password": "password123"})
    assert res.status_code == 409


def test_short_password_is_rejected(client):
    res = client.post("/auth/signup", json={"email": "a@example.com", "password": "short"})
    assert res.status_code == 422


def test_login(client):
    signup(client)
    ok = client.post("/auth/login", json={"email": "me@example.com", "password": "password123"})
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = client.post("/auth/login", json={"email": "me@example.com", "password": "wrong-password"})
    assert bad.status_code == 401
    nobody = client.post("/auth/login", json={"email": "no@example.com", "password": "password123"})
    assert nobody.status_code == 401


def test_protected_endpoints_require_token(client):
    assert client.get("/me").status_code == 401
    assert client.get("/sessions").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_delete_me_invalidates_token(client):
    headers = signup(client)
    assert client.delete("/me", headers=headers).status_code == 204
    assert client.get("/me", headers=headers).status_code == 401
    # 같은 이메일로 다시 가입 가능
    signup(client)
