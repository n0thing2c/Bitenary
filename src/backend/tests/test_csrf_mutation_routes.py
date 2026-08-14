from uuid import UUID, uuid4

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
import pytest

from api.chat import router as chat_router
from core.csrf import CSRFMiddleware, create_csrf_token
from health_profile.domain.entities import (
    HealthProfileOnboardingState,
    HealthProfileState,
)
from health_profile.wiring import get_health_profile_service
from identity.domain.entities import CurrentUser, UserStatus
from identity.wiring import get_current_user
from core.config import get_settings
from guest_chat.service import (
    GUEST_COOKIE_NAME,
    GUEST_COOKIE_PATH,
    GuestChatRateLimitExceeded,
    GuestIdentityCodec,
)
from meal_plan.delivery.routes import router as meal_plan_router
from meal_plan.wiring import get_meal_plan_service
from virtual_fridge.wiring import get_virtual_fridge_service


CSRF_SECRET = "mutation-route-test-secret"


class FakeOrchestrator:
    def __init__(self) -> None:
        self.chat_calls = 0
        self.clear_history_calls = 0
        self.last_chat_values: dict[str, object] | None = None
        self.chat_values: list[dict[str, object]] = []

    async def chat(self, **values: object) -> str:
        self.chat_calls += 1
        self.last_chat_values = values
        self.chat_values.append(values)
        return "AI reply"

    async def clear_history(self, **_values: object) -> None:
        self.clear_history_calls += 1


class FakeProfileService:
    async def get_state(self, _user_id: UUID) -> HealthProfileState:
        return HealthProfileState(
            onboarding_state=HealthProfileOnboardingState.SKIPPED,
            profile=None,
        )


class FakeFridgeService:
    async def get_available_ingredients(self, **_values: object) -> tuple[()]:
        return ()


class FakeMealPlanService:
    def __init__(self) -> None:
        self.delete_calls = 0

    async def delete_plan(self, **_values: object) -> None:
        self.delete_calls += 1


class FakeGuestChatRateLimiter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.error: Exception | None = None

    async def check(self, **values: object) -> None:
        self.calls.append(values)
        if self.error is not None:
            raise self.error


@pytest.fixture()
def mutation_client() -> tuple[TestClient, FakeOrchestrator, FakeMealPlanService]:
    current_user = CurrentUser(
        user_id=uuid4(),
        authentik_sub="authentik-user-1",
        username="Ada",
        email="ada@example.com",
        status=UserStatus.ACTIVE,
    )
    orchestrator = FakeOrchestrator()
    meal_plan_service = FakeMealPlanService()
    app = FastAPI()
    app.add_middleware(CSRFMiddleware, secret=CSRF_SECRET)
    api_router = APIRouter(prefix="/api")
    api_router.include_router(chat_router)
    api_router.include_router(meal_plan_router)
    app.include_router(api_router)
    app.state.orchestrator = orchestrator
    app.state.guest_chat_rate_limiter = FakeGuestChatRateLimiter()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_health_profile_service] = FakeProfileService
    app.dependency_overrides[get_virtual_fridge_service] = FakeFridgeService
    app.dependency_overrides[get_meal_plan_service] = lambda: meal_plan_service

    with TestClient(app) as client:
        yield client, orchestrator, meal_plan_service


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = create_csrf_token(CSRF_SECRET)
    client.cookies.set("bitenary_csrf", token)
    return {"X-CSRF-Token": token}


@pytest.mark.parametrize("forged", [False, True])
def test_chat_post_rejects_missing_or_forged_csrf_before_calling_orchestrator(
    mutation_client: tuple[TestClient, FakeOrchestrator, FakeMealPlanService],
    forged: bool,
) -> None:
    client, orchestrator, _meal_plan_service = mutation_client
    headers = {}
    if forged:
        client.cookies.set("bitenary_csrf", "forged-token")
        headers = {"X-CSRF-Token": "forged-token"}

    response = client.post(
        "/api/chat",
        headers=headers,
        json={"session_id": "session-1", "message": "Hello"},
    )

    assert response.status_code == 403
    assert orchestrator.chat_calls == 0


def test_chat_post_accepts_signed_csrf(
    mutation_client: tuple[TestClient, FakeOrchestrator, FakeMealPlanService],
) -> None:
    client, orchestrator, _meal_plan_service = mutation_client

    response = client.post(
        "/api/chat",
        headers=csrf_headers(client),
        json={"session_id": "session-1", "message": "Hello"},
    )

    assert response.status_code == 200
    assert response.json() == {"session_id": "session-1", "reply": "AI reply"}
    assert orchestrator.chat_calls == 1


@pytest.mark.parametrize("forged", [False, True])
def test_guest_chat_rejects_missing_or_forged_csrf(
    mutation_client: tuple[TestClient, FakeOrchestrator, FakeMealPlanService],
    forged: bool,
) -> None:
    client, orchestrator, _meal_plan_service = mutation_client
    headers = {}
    if forged:
        client.cookies.set("bitenary_csrf", "forged-token")
        headers = {"X-CSRF-Token": "forged-token"}

    response = client.post(
        "/api/chat/guest",
        headers=headers,
        json={"session_id": "guest-session", "message": "Hello"},
    )

    assert response.status_code == 403
    assert orchestrator.chat_calls == 0


def test_guest_chat_works_without_authenticated_user_and_sets_cookie(
    mutation_client: tuple[TestClient, FakeOrchestrator, FakeMealPlanService],
) -> None:
    client, orchestrator, _meal_plan_service = mutation_client
    original_override = client.app.dependency_overrides[get_current_user]

    def reject_auth_dependency() -> None:
        raise AssertionError("Guest chat must not resolve an authenticated user")

    client.app.dependency_overrides[get_current_user] = reject_auth_dependency
    try:
        response = client.post(
            "/api/chat/guest",
            headers=csrf_headers(client),
            json={"session_id": "guest-session", "message": "Plan dinner"},
        )
    finally:
        client.app.dependency_overrides[get_current_user] = original_override

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "guest-session",
        "reply": "AI reply",
    }
    assert response.cookies.get(GUEST_COOKIE_NAME)
    assert orchestrator.last_chat_values is not None
    assert str(orchestrator.last_chat_values["mode"]) == "guest"
    assert orchestrator.last_chat_values["health_profile"] is None
    assert orchestrator.last_chat_values["expiring_items"] is None


def test_guest_chat_reuses_valid_cookie_identity(
    mutation_client: tuple[TestClient, FakeOrchestrator, FakeMealPlanService],
) -> None:
    client, orchestrator, _meal_plan_service = mutation_client
    headers = csrf_headers(client)

    for message in ("First", "Second"):
        response = client.post(
            "/api/chat/guest",
            headers=headers,
            json={"session_id": "guest-session", "message": message},
        )
        assert response.status_code == 200

    assert len(orchestrator.chat_values) == 2
    assert orchestrator.chat_values[0]["user_id"] == orchestrator.chat_values[1]["user_id"]


def test_guest_chat_replaces_tampered_identity_cookie(
    mutation_client: tuple[TestClient, FakeOrchestrator, FakeMealPlanService],
) -> None:
    client, _orchestrator, _meal_plan_service = mutation_client
    client.cookies.set(GUEST_COOKIE_NAME, "tampered", path=GUEST_COOKIE_PATH)

    response = client.post(
        "/api/chat/guest",
        headers=csrf_headers(client),
        json={"session_id": "guest-session", "message": "Hello"},
    )

    assert response.status_code == 200
    replacement = response.cookies.get(GUEST_COOKIE_NAME)
    assert replacement is not None
    assert GuestIdentityCodec(get_settings().csrf_secret).decode(replacement) is not None


def test_guest_chat_returns_rate_limit_with_retry_after(
    mutation_client: tuple[TestClient, FakeOrchestrator, FakeMealPlanService],
) -> None:
    client, orchestrator, _meal_plan_service = mutation_client
    limiter = client.app.state.guest_chat_rate_limiter
    limiter.error = GuestChatRateLimitExceeded(retry_after=37)

    response = client.post(
        "/api/chat/guest",
        headers=csrf_headers(client),
        json={"session_id": "guest-session", "message": "Hello"},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "37"
    assert orchestrator.chat_calls == 0


def test_guest_chat_fails_closed_when_rate_limiter_is_unavailable(
    mutation_client: tuple[TestClient, FakeOrchestrator, FakeMealPlanService],
) -> None:
    client, orchestrator, _meal_plan_service = mutation_client
    limiter = client.app.state.guest_chat_rate_limiter
    limiter.error = RuntimeError("redis unavailable")

    response = client.post(
        "/api/chat/guest",
        headers=csrf_headers(client),
        json={"session_id": "guest-session", "message": "Hello"},
    )

    assert response.status_code == 503
    assert orchestrator.chat_calls == 0


@pytest.mark.parametrize("forged", [False, True])
def test_clear_history_rejects_missing_or_forged_csrf_before_calling_orchestrator(
    mutation_client: tuple[TestClient, FakeOrchestrator, FakeMealPlanService],
    forged: bool,
) -> None:
    client, orchestrator, _meal_plan_service = mutation_client
    headers = {}
    if forged:
        client.cookies.set("bitenary_csrf", "forged-token")
        headers = {"X-CSRF-Token": "forged-token"}

    response = client.request(
        "DELETE",
        "/api/chat/history",
        headers=headers,
        json={"session_id": "session-1"},
    )

    assert response.status_code == 403
    assert orchestrator.clear_history_calls == 0


def test_clear_history_accepts_signed_csrf(
    mutation_client: tuple[TestClient, FakeOrchestrator, FakeMealPlanService],
) -> None:
    client, orchestrator, _meal_plan_service = mutation_client

    response = client.request(
        "DELETE",
        "/api/chat/history",
        headers=csrf_headers(client),
        json={"session_id": "session-1"},
    )

    assert response.status_code == 204
    assert orchestrator.clear_history_calls == 1


@pytest.mark.parametrize("forged", [False, True])
def test_delete_meal_plan_rejects_missing_or_forged_csrf_before_service_call(
    mutation_client: tuple[TestClient, FakeOrchestrator, FakeMealPlanService],
    forged: bool,
) -> None:
    client, _orchestrator, meal_plan_service = mutation_client
    headers = {}
    if forged:
        client.cookies.set("bitenary_csrf", "forged-token")
        headers = {"X-CSRF-Token": "forged-token"}

    response = client.delete(f"/api/meal-plans/{uuid4()}", headers=headers)

    assert response.status_code == 403
    assert meal_plan_service.delete_calls == 0


def test_delete_meal_plan_accepts_signed_csrf(
    mutation_client: tuple[TestClient, FakeOrchestrator, FakeMealPlanService],
) -> None:
    client, _orchestrator, meal_plan_service = mutation_client

    response = client.delete(
        f"/api/meal-plans/{uuid4()}",
        headers=csrf_headers(client),
    )

    assert response.status_code == 204
    assert meal_plan_service.delete_calls == 1
