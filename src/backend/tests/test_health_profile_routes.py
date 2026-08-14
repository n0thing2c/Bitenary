from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from conftest import csrf_headers
from app.main import create_app
from health_profile.domain.entities import (
    HealthPreference,
    HealthPreferenceType,
    HealthProfile,
    HealthProfileActivityLevel,
    HealthProfileGender,
    HealthProfileOnboardingState,
    HealthProfilePrimaryGoal,
    HealthProfileState,
)
from health_profile.wiring import get_health_profile_service
from identity.domain.entities import CurrentUser, UserStatus
from identity.wiring import get_current_user


class FakeHealthProfileService:
    def __init__(self) -> None:
        self.state = HealthProfileState(
            onboarding_state=HealthProfileOnboardingState.NOT_STARTED,
            profile=None,
        )
        self.saved_values: dict[str, object] | None = None

    async def get_state(self, _user_id: UUID) -> HealthProfileState:
        return self.state

    async def save(self, **values: object) -> HealthProfile:
        self.saved_values = values
        now = datetime.now(UTC)
        user_id = values["user_id"]
        preferences = values["preferences"]
        profile = HealthProfile(
            user_id=user_id,  # type: ignore[arg-type]
            date_of_birth=values["date_of_birth"],  # type: ignore[arg-type]
            gender=values["gender"],  # type: ignore[arg-type]
            weight_kg=values["weight_kg"],  # type: ignore[arg-type]
            height_cm=values["height_cm"],  # type: ignore[arg-type]
            activity_level=values["activity_level"],  # type: ignore[arg-type]
            primary_goal=values["primary_goal"],  # type: ignore[arg-type]
            target_weight_kg=values["target_weight_kg"],  # type: ignore[arg-type]
            preferences=tuple(
                HealthPreference(
                    preference_id=uuid4(),
                    preference_type=preference_type,
                    value=value,
                    normalized_value=value.casefold(),
                    created_at=now,
                )
                for preference_type, value in preferences  # type: ignore[union-attr]
            ),
            created_at=now,
            updated_at=now,
        )
        self.state = HealthProfileState(
            onboarding_state=HealthProfileOnboardingState.COMPLETED,
            profile=profile,
        )
        return profile

    async def skip_onboarding(self, _user_id: UUID) -> HealthProfileState:
        self.state = HealthProfileState(
            onboarding_state=HealthProfileOnboardingState.SKIPPED,
            profile=None,
        )
        return self.state


@pytest.fixture()
def health_profile_client() -> tuple[
    TestClient,
    FakeHealthProfileService,
    CurrentUser,
]:
    current_user = CurrentUser(
        user_id=uuid4(),
        authentik_sub="authentik-user-1",
        username="Ada",
        email="ada@example.com",
        status=UserStatus.ACTIVE,
    )
    service = FakeHealthProfileService()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_health_profile_service] = lambda: service
    with TestClient(app) as client:
        yield client, service, current_user
    app.dependency_overrides.clear()


def valid_profile_payload() -> dict[str, object]:
    return {
        "date_of_birth": "1995-04-12",
        "gender": "FEMALE",
        "weight_kg": 62.5,
        "height_cm": 168,
        "activity_level": "MODERATE",
        "primary_goal": "MAINTAIN",
        "target_weight_kg": None,
        "preferences": [
            {"preference_type": "ALLERGY", "value": "Tree nuts"},
            {"preference_type": "TASTE", "value": "Spicy"},
        ],
    }


def test_get_profile_returns_account_and_not_started_state(
    health_profile_client: tuple[TestClient, FakeHealthProfileService, CurrentUser],
) -> None:
    client, _service, current_user = health_profile_client

    response = client.get("/api/health-profile")

    assert response.status_code == 200
    assert response.json() == {
        "onboarding_state": "NOT_STARTED",
        "account": {
            "user_id": str(current_user.user_id),
            "username": "Ada",
            "email": "ada@example.com",
            "status": "ACTIVE",
        },
        "health_profile": None,
    }


def test_put_profile_requires_csrf(
    health_profile_client: tuple[TestClient, FakeHealthProfileService, CurrentUser],
) -> None:
    client, _service, _current_user = health_profile_client

    response = client.put("/api/health-profile", json=valid_profile_payload())

    assert response.status_code == 403


def test_put_profile_creates_completed_profile(
    health_profile_client: tuple[TestClient, FakeHealthProfileService, CurrentUser],
) -> None:
    client, service, current_user = health_profile_client
    response = client.put(
        "/api/health-profile",
        headers=csrf_headers(client),
        json=valid_profile_payload(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["onboarding_state"] == "COMPLETED"
    assert payload["health_profile"]["date_of_birth"] == "1995-04-12"
    assert payload["health_profile"]["weight_kg"] == 62.5
    assert payload["health_profile"]["preferences"] == [
        {"preference_type": "ALLERGY", "value": "Tree nuts"},
        {"preference_type": "TASTE", "value": "Spicy"},
    ]
    assert service.saved_values is not None
    assert service.saved_values["user_id"] == current_user.user_id


def test_put_profile_rejects_future_date(
    health_profile_client: tuple[TestClient, FakeHealthProfileService, CurrentUser],
) -> None:
    client, _service, _current_user = health_profile_client
    payload = valid_profile_payload()
    payload["date_of_birth"] = date.today().isoformat()

    response = client.put(
        "/api/health-profile",
        headers=csrf_headers(client),
        json=payload,
    )

    assert response.status_code == 422


def test_skip_onboarding_requires_csrf_and_persists_state(
    health_profile_client: tuple[TestClient, FakeHealthProfileService, CurrentUser],
) -> None:
    client, service, _current_user = health_profile_client

    assert client.post("/api/health-profile/onboarding/skip").status_code == 403

    response = client.post(
        "/api/health-profile/onboarding/skip",
        headers=csrf_headers(client),
    )

    assert response.status_code == 204
    assert service.state.onboarding_state == HealthProfileOnboardingState.SKIPPED


def test_get_profile_requires_authentication() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/health-profile")

    assert response.status_code == 401
