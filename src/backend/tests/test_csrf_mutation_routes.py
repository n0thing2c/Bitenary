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
from meal_plan.delivery.routes import router as meal_plan_router
from meal_plan.wiring import get_meal_plan_service
from virtual_fridge.wiring import get_virtual_fridge_service


CSRF_SECRET = "mutation-route-test-secret"


class FakeOrchestrator:
    def __init__(self) -> None:
        self.chat_calls = 0
        self.clear_history_calls = 0

    async def chat(self, **_values: object) -> str:
        self.chat_calls += 1
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
