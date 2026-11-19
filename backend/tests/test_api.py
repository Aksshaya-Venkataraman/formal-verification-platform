import pytest
from conftest import PASSWORD, ApiClient, needs_provers
from sqlalchemy import select

from fvp.models import User

SOCRATES = """fof(a, axiom, ![X]: (man(X) => mortal(X))).
fof(b, axiom, man(socrates)).
fof(c, conjecture, mortal(socrates)).
"""


# ------------------------------------------------------------------- auth
def test_register_login_me_logout(client):
    client.register("Alice@Example.com")
    assert client.get("/api/auth/me").get_json()["user"]["email"] == "alice@example.com"
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").get_json()["user"] is None
    resp = client.post("/api/auth/login", json={"email": "alice@example.com", "password": PASSWORD})
    assert resp.status_code == 200


def test_passwords_hashed_with_argon2(app, user):
    with app.app_context():
        session = app.extensions["fvp.session_factory"]()
        stored = session.scalar(select(User)).password_hash
    assert stored.startswith("$argon2id$")


def test_login_failure_is_generic(user, app):
    fresh = ApiClient(app)
    wrong = fresh.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrong-password-1"})
    ghost = fresh.post("/api/auth/login", json={"email": "ghost@example.com", "password": PASSWORD})
    assert wrong.status_code == ghost.status_code == 401
    assert wrong.get_json() == ghost.get_json()


def test_duplicate_registration_is_generic(user, app):
    resp = ApiClient(app).post("/api/auth/register", json={"email": "alice@example.com", "password": PASSWORD})
    assert resp.status_code == 400
    assert resp.get_json()["message"] == "Registration failed."


@pytest.mark.parametrize("password", ["short", "aaaaaaaaaaaaaaa"])
def test_weak_passwords_rejected(client, password):
    assert client.post("/api/auth/register", json={"email": "w@example.com", "password": password}).status_code == 422


def test_session_cookie_flags(app):
    c = ApiClient(app)
    response = c.post("/api/auth/register", json={"email": "c@example.com", "password": PASSWORD})
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie


def test_production_cookie_is_secure_host_prefixed(make_app):
    app = make_app(environment="production")
    response = app.test_client().get("/api/auth/csrf")
    cookie = response.headers["Set-Cookie"]
    assert cookie.startswith("__Host-fvp_session=")
    assert "Secure" in cookie
    assert "Strict-Transport-Security" in response.headers


def test_password_change_signs_out_other_sessions(app, user):
    second_device = ApiClient(app)
    second_device.post("/api/auth/login", json={"email": "alice@example.com", "password": PASSWORD})
    assert second_device.get("/api/auth/me").get_json()["user"] is not None
    resp = user.post(
        "/api/auth/change-password", json={"current_password": PASSWORD, "new_password": "a-different-password-2"}
    )
    assert resp.status_code == 200
    assert user.get("/api/auth/me").get_json()["user"] is not None  # this device stays signed in
    assert second_device.get("/api/auth/me").get_json()["user"] is None  # the other one is signed out


def test_logout_everywhere(app, user):
    second_device = ApiClient(app)
    second_device.post("/api/auth/login", json={"email": "alice@example.com", "password": PASSWORD})
    assert user.post("/api/auth/logout-all").status_code == 200
    assert second_device.get("/api/auth/me").get_json()["user"] is None


def test_login_rate_limit(make_app):
    c = ApiClient(make_app(login_rate_limit="3/minute"))
    body = {"email": "brute@example.com", "password": "guess-guess-guess"}
    assert [c.post("/api/auth/login", json=body).status_code for _ in range(4)] == [401, 401, 401, 429]


# ------------------------------------------------------------------- CSRF
def test_state_changes_require_csrf_token(user):
    raw = user.http
    assert raw.post("/api/validate", json={"source": SOCRATES}).status_code == 403
    assert raw.post("/api/validate", json={"source": SOCRATES}, headers={"X-CSRF-Token": "forged"}).status_code == 403
    assert user.post("/api/validate", json={"source": SOCRATES}).status_code == 200


def test_cross_origin_requests_rejected(user):
    resp = user.post("/api/validate", json={"source": SOCRATES}, headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403
    ok = user.post("/api/validate", json={"source": SOCRATES}, headers={"Origin": "http://localhost"})
    assert ok.status_code == 200


# ------------------------------------------------------------ verification
def test_validate_reports_structure_and_syntax_errors(user):
    info = user.post("/api/validate", json={"source": SOCRATES}).get_json()
    assert info["formulas"] == 3 and info["has_conjecture"] is True
    assert info["predicates"] == ["man/1", "mortal/1"]
    bad = user.post("/api/validate", json={"source": "fof(a, axiom, p(X))."})
    assert bad.status_code == 400
    assert bad.get_json()["line"] == 1


def test_endpoints_require_login(client):
    for method, url in [
        ("post", "/api/verify"),
        ("post", "/api/validate"),
        ("get", "/api/runs"),
        ("get", "/api/problems"),
        ("get", "/api/admin/stats"),
    ]:
        assert getattr(client, method)(url, json={}).status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        {"source": SOCRATES, "provers": []},
        {"source": SOCRATES, "provers": ["spass", "spass"]},
        {"source": SOCRATES, "provers": ["eprover"]},
        {"source": SOCRATES, "provers": ["spass"], "time_limit": 0},
        {"source": SOCRATES, "provers": ["spass"], "time_limit": 11},
        {"source": SOCRATES, "provers": ["spass"], "title": "<script>alert(1)</script>"},
        {"source": SOCRATES, "provers": ["spass"], "extra": True},
        {"source": "x" * 70_000, "provers": ["spass"]},
    ],
    ids=[
        "no-provers",
        "duplicate",
        "unknown-prover",
        "zero-time",
        "over-max-time",
        "xss-title",
        "extra-field",
        "too-large",
    ],
)
def test_verify_rejects_invalid_requests(user, body):
    assert user.post("/api/verify", json=body).status_code in (413, 422)


def test_verify_rejects_unsafe_tptp(user):
    resp = user.post("/api/verify", json={"source": "include('/etc/passwd').", "provers": ["spass"]})
    assert resp.status_code == 400
    assert "include" in resp.get_json()["message"]


@needs_provers
def test_verify_end_to_end_and_history(user, other):
    resp = user.post(
        "/api/verify",
        json={"source": SOCRATES, "provers": ["spass", "vampire", "otter"], "time_limit": 5, "title": "Socrates"},
    )
    assert resp.status_code == 201
    run = resp.get_json()
    assert run["verdict"] == "theorem"
    assert run["statuses"] == {"spass": "Theorem", "vampire": "Theorem", "otter": "Theorem"}
    assert all(r["output"] for r in run["results"])

    history = user.get("/api/runs").get_json()
    assert history["total"] == 1 and "results" not in history["runs"][0]
    assert user.get(f"/api/runs/{run['id']}").get_json()["source"] == SOCRATES

    # Another user can neither see nor delete it.
    assert other.get(f"/api/runs/{run['id']}").status_code == 404
    assert other.delete(f"/api/runs/{run['id']}").status_code == 404
    assert other.get("/api/runs").get_json()["total"] == 0
    assert user.delete(f"/api/runs/{run['id']}").status_code == 204


# ---------------------------------------------------------------- problems
def test_problem_library_is_private(user, other):
    body = {"title": "Socrates", "domain": "First-order logic", "description": "Syllogism", "source": SOCRATES}
    created = user.post("/api/problems", json=body)
    assert created.status_code == 201
    pid = created.get_json()["id"]
    assert user.post("/api/problems", json=body).status_code == 409
    assert other.get(f"/api/problems/{pid}").status_code == 404
    assert other.put(f"/api/problems/{pid}", json=body).status_code == 404
    assert other.delete(f"/api/problems/{pid}").status_code == 404
    assert other.get("/api/problems").get_json()["problems"] == []
    updated = user.put(f"/api/problems/{pid}", json={**body, "description": "Updated"})
    assert updated.get_json()["description"] == "Updated"
    assert user.put(f"/api/problems/{pid}", json={**body, "source": "fof(a, axiom, p(X))."}).status_code == 400
    assert user.delete(f"/api/problems/{pid}").status_code == 204


# -------------------------------------------------------------- admin/ops
def test_admin_stats_requires_admin(app, user):
    assert user.get("/api/admin/stats").status_code == 403
    with app.app_context():
        session = app.extensions["fvp.session_factory"]()
        session.scalar(select(User)).is_admin = True
        session.commit()
    stats = user.get("/api/admin/stats").get_json()
    assert stats["users"] == 1
    assert {p["name"] for p in stats["provers"]} == {"spass", "vampire", "otter"}


def test_public_endpoints_and_headers(client):
    resp = client.get("/api/health")
    assert resp.get_json() == {"status": "ok"}
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert resp.headers["Cache-Control"] == "no-store"
    assert client.get("/api/ready").get_json()["database"] == "ok"
    assert len(client.get("/api/examples").get_json()["examples"]) >= 10
    assert client.get("/api/nope").status_code == 404
    assert client.get("/api/nope").get_json()["error"] == "not_found"


def test_unknown_host_rejected(client):
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
    assert client.get("/api/health", headers={"Host": "backend:8000"}).status_code == 200


def test_body_size_limit(user):
    resp = user.post("/api/validate", data="x" * 300_000, headers={"Content-Type": "application/json"})
    assert resp.status_code == 413


@pytest.mark.parametrize(
    "overrides",
    [{"secret_key": "short"}, {"secret_key": "change-me-" + "a" * 40}, {"allowed_origins": "*"}],
)
def test_insecure_settings_refused(overrides):
    from conftest import make_settings

    with pytest.raises(ValueError):
        make_settings(**overrides)
