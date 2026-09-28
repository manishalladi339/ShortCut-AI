"""Pure routing tests for public-beta request guards."""
from services.public_beta_guard import route_policy


def test_auth_routes_are_rate_limited():
    policy = route_policy("POST", "/api/v1/auth/login")
    assert policy is not None
    assert policy.scope == "auth"
    assert policy.limit > 0


def test_render_routes_are_rate_limited():
    policy = route_policy("POST", "/api/v1/projects/project-1/exports")
    assert policy is not None
    assert policy.scope == "render"


def test_ai_routes_are_rate_limited():
    assert route_policy("POST", "/api/v1/assets/asset-1/analyze").scope == "ai"
    assert route_policy("POST", "/api/v1/projects/p1/ai-plans").scope == "ai"
    assert route_policy("POST", "/api/v1/projects/p1/constrained-edits").scope == "ai"


def test_read_only_routes_do_not_consume_rate_bucket():
    assert route_policy("GET", "/api/v1/projects") is None
    assert route_policy("GET", "/api/v1/assets/a1/intelligence") is None
