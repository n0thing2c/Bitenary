"""Tests for agents/prompts.py and agents/orchestrator.py.

Coverage:
    - build_system_prompt() with no profile (anonymous user)
    - build_system_prompt() with a complete profile (personalised)
    - Allergy safety warning is injected when allergies exist
    - Allergy safety warning is NOT injected for plain dislikes
    - _calculate_age() boundary conditions
    - BitenaryChatOrchestrator.chat() happy-path (MCP + Gemini mocked)
    - BitenaryChatOrchestrator raises RuntimeError if not started
    - BitenaryChatOrchestrator.clear_history() deletes correct Redis key
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Patch settings before any module that imports core.config is loaded
# ---------------------------------------------------------------------------
os.environ.setdefault("SPOONACULAR_API_KEY", "test-key")
os.environ.setdefault("GOOGLE_API_KEY", "test-gemini-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

from agents.prompts import _calculate_age, build_system_prompt  # noqa: E402
from health_profile.domain.entities import (  # noqa: E402
    HealthPreference,
    HealthPreferenceType,
    HealthProfile,
    HealthProfileActivityLevel,
    HealthProfileGender,
    HealthProfilePrimaryGoal,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FIXED_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
_FIXED_SESSION = "session-abc"


def _make_profile(
    *,
    dob: date = date(1995, 6, 15),
    gender: HealthProfileGender = HealthProfileGender.MALE,
    weight_kg: Decimal = Decimal("75"),
    height_cm: Decimal = Decimal("175"),
    activity_level: HealthProfileActivityLevel = HealthProfileActivityLevel.MODERATE,
    primary_goal: HealthProfilePrimaryGoal = HealthProfilePrimaryGoal.WEIGHT_LOSS,
    target_weight_kg: Decimal | None = Decimal("68"),
    preferences: tuple[HealthPreference, ...] = (),
) -> HealthProfile:
    """Build a HealthProfile fixture without hitting the database."""
    return HealthProfile(
        user_id=_FIXED_USER_ID,
        date_of_birth=dob,
        gender=gender,
        weight_kg=weight_kg,
        height_cm=height_cm,
        activity_level=activity_level,
        primary_goal=primary_goal,
        target_weight_kg=target_weight_kg,
        preferences=preferences,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_preference(
    pref_type: HealthPreferenceType,
    value: str,
) -> HealthPreference:
    return HealthPreference(
        preference_id=uuid4(),
        preference_type=pref_type,
        value=value,
        normalized_value=value.casefold(),
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Tests: build_system_prompt()
# ---------------------------------------------------------------------------


class TestBuildSystemPromptAnonymous:
    """When no profile is available, only the base prompt is returned."""

    def test_returns_base_prompt_when_no_profile(self):
        prompt = build_system_prompt(None)
        assert "Bitenary AI" in prompt
        assert "Medical Disclaimer" in prompt

    def test_no_profile_block_injected(self):
        prompt = build_system_prompt(None)
        assert "Health Profile" not in prompt
        assert "Weight:" not in prompt

    def test_no_allergy_warning_without_profile(self):
        prompt = build_system_prompt(None)
        assert "CRITICAL SAFETY RULE" not in prompt


class TestBuildSystemPromptPersonalised:
    """When a profile exists, the personalised context block is appended."""

    def test_contains_weight_and_height(self):
        profile = _make_profile(weight_kg=Decimal("80"), height_cm=Decimal("180"))
        prompt = build_system_prompt(profile)
        assert "80" in prompt
        assert "180" in prompt

    def test_contains_primary_goal_label(self):
        profile = _make_profile(primary_goal=HealthProfilePrimaryGoal.MUSCLE_GAIN)
        prompt = build_system_prompt(profile)
        assert "Build muscle" in prompt

    def test_contains_target_weight_when_set(self):
        profile = _make_profile(target_weight_kg=Decimal("65"))
        prompt = build_system_prompt(profile)
        assert "65" in prompt

    def test_no_target_weight_when_none(self):
        profile = _make_profile(target_weight_kg=None)
        prompt = build_system_prompt(profile)
        assert "Target Weight" not in prompt

    def test_contains_age(self):
        # Born exactly 30 years ago (± birthday tolerance is fine)
        today = datetime.now(UTC).date()
        dob = date(today.year - 30, today.month, today.day)
        profile = _make_profile(dob=dob)
        prompt = build_system_prompt(profile)
        assert "30" in prompt

    def test_allergy_injected_in_prompt(self):
        pref = _make_preference(HealthPreferenceType.ALLERGY, "peanuts")
        profile = _make_profile(preferences=(pref,))
        prompt = build_system_prompt(profile)
        assert "peanuts" in prompt
        assert "DANGER" in prompt

    def test_critical_safety_rule_injected_when_allergy_exists(self):
        pref = _make_preference(HealthPreferenceType.ALLERGY, "shellfish")
        profile = _make_profile(preferences=(pref,))
        prompt = build_system_prompt(profile)
        assert "CRITICAL SAFETY RULE" in prompt

    def test_critical_safety_rule_injected_when_dietary_restriction_exists(self):
        pref = _make_preference(HealthPreferenceType.DIETARY_RESTRICTION, "vegan")
        profile = _make_profile(preferences=(pref,))
        prompt = build_system_prompt(profile)
        assert "CRITICAL SAFETY RULE" in prompt

    def test_no_critical_safety_rule_for_plain_dislikes(self):
        pref = _make_preference(HealthPreferenceType.DISLIKE, "broccoli")
        profile = _make_profile(preferences=(pref,))
        prompt = build_system_prompt(profile)
        # Dislikes should appear but NOT trigger the critical safety warning
        assert "broccoli" in prompt
        assert "CRITICAL SAFETY RULE" not in prompt

    def test_multiple_allergies_joined(self):
        prefs = (
            _make_preference(HealthPreferenceType.ALLERGY, "peanuts"),
            _make_preference(HealthPreferenceType.ALLERGY, "tree nuts"),
        )
        profile = _make_profile(preferences=prefs)
        prompt = build_system_prompt(profile)
        assert "peanuts" in prompt
        assert "tree nuts" in prompt

    def test_base_rules_still_present_with_profile(self):
        profile = _make_profile()
        prompt = build_system_prompt(profile)
        assert "calculate_nutrition" in prompt
        assert "Medical Disclaimer" in prompt


# ---------------------------------------------------------------------------
# Tests: _calculate_age()
# ---------------------------------------------------------------------------


class TestCalculateAge:
    def test_exact_birthday_today(self):
        today = datetime.now(UTC).date()
        dob = date(today.year - 25, today.month, today.day)
        assert _calculate_age(dob) == 25

    def test_birthday_tomorrow(self):
        tomorrow = datetime.now(UTC).date() + timedelta(days=1)
        dob = date(tomorrow.year - 20, tomorrow.month, tomorrow.day)
        # Birthday has not occurred yet this year → still 19
        assert _calculate_age(dob) == 19

    def test_birthday_yesterday(self):
        yesterday = datetime.now(UTC).date() - timedelta(days=1)
        dob = date(yesterday.year - 30, yesterday.month, yesterday.day)
        # Birthday already passed → 30
        assert _calculate_age(dob) == 30


# ---------------------------------------------------------------------------
# Tests: BitenaryChatOrchestrator
# ---------------------------------------------------------------------------


class TestOrchestratorNotStarted:
    def test_chat_raises_if_not_started(self):
        """chat() must raise RuntimeError before startup() is called."""
        from core.config import get_settings
        from agents.orchestrator import BitenaryChatOrchestrator
        from bitenary_mcp.service.tokens import MCPTokenCodec

        orchestrator = BitenaryChatOrchestrator(
            get_settings(),
            MCPTokenCodec(get_settings().mcp_token_pepper),
        )

        import asyncio

        with pytest.raises(RuntimeError, match="not started"):
            asyncio.get_event_loop().run_until_complete(
                orchestrator.chat(
                    user_id=_FIXED_USER_ID,
                    session_id=_FIXED_SESSION,
                    user_message="hello",
                )
            )


class TestOrchestratorHappyPath:
    """Mock Gemini and MCP so we can test the Orchestrator's own logic."""

    @pytest.fixture()
    def mock_redis(self):
        redis = AsyncMock()
        redis.lrange = AsyncMock(return_value=[])
        redis.rpush = AsyncMock(return_value=1)
        redis.expire = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        return redis

    @pytest.fixture()
    def orchestrator(self, mock_redis):
        from core.config import get_settings
        from agents.orchestrator import BitenaryChatOrchestrator
        from bitenary_mcp.service.tokens import MCPTokenCodec

        settings = get_settings()
        orch = BitenaryChatOrchestrator(
            settings,
            MCPTokenCodec(settings.mcp_token_pepper),
        )
        orch._redis = mock_redis  # inject without real Redis connection
        return orch

    @pytest.mark.asyncio
    async def test_chat_returns_ai_reply(self, orchestrator):
        """When Gemini + MCP are mocked, orchestrator.chat() returns AI text."""
        from langchain_core.messages import AIMessage

        fake_ai_msg = AIMessage(content="Pho bo khoang 450 calo.")
        fake_agent_result = {"messages": [fake_ai_msg]}

        mock_mcp_client = MagicMock()
        mock_mcp_client.get_tools = MagicMock(return_value=[])
        mock_mcp_ctx = MagicMock()
        mock_mcp_ctx.__aenter__ = AsyncMock(return_value=mock_mcp_client)
        mock_mcp_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "agents.orchestrator.MultiServerMCPClient",
                return_value=mock_mcp_ctx,
            ),
            patch(
                "agents.orchestrator.create_react_agent",
                return_value=MagicMock(
                    ainvoke=AsyncMock(return_value=fake_agent_result)
                ),
            ),
        ):
            reply = await orchestrator.chat(
                user_id=_FIXED_USER_ID,
                session_id=_FIXED_SESSION,
                user_message="Pho bo bao nhieu calo?",
            )

        assert "450" in reply

    @pytest.mark.asyncio
    async def test_chat_saves_turn_to_redis(self, orchestrator, mock_redis):
        """After chat(), rpush is called to persist the conversation turn."""
        from langchain_core.messages import AIMessage

        fake_agent_result = {"messages": [AIMessage(content="test reply")]}

        mock_mcp_client = MagicMock()
        mock_mcp_client.get_tools = MagicMock(return_value=[])
        mock_mcp_ctx = MagicMock()
        mock_mcp_ctx.__aenter__ = AsyncMock(return_value=mock_mcp_client)
        mock_mcp_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("agents.orchestrator.MultiServerMCPClient", return_value=mock_mcp_ctx),
            patch(
                "agents.orchestrator.create_react_agent",
                return_value=MagicMock(
                    ainvoke=AsyncMock(return_value=fake_agent_result)
                ),
            ),
        ):
            await orchestrator.chat(
                user_id=_FIXED_USER_ID,
                session_id=_FIXED_SESSION,
                user_message="test message",
            )

        mock_redis.rpush.assert_called_once()
        # Ensure the scoped key format is used
        call_args = mock_redis.rpush.call_args[0]
        assert str(_FIXED_USER_ID) in call_args[0]
        assert _FIXED_SESSION in call_args[0]

    @pytest.mark.asyncio
    async def test_chat_with_health_profile_injects_allergy(self, orchestrator):
        """System prompt built during chat should contain user's allergy."""
        pref = _make_preference(HealthPreferenceType.ALLERGY, "peanuts")
        profile = _make_profile(preferences=(pref,))

        captured_messages: list = []

        async def capture_ainvoke(inputs):
            captured_messages.extend(inputs["messages"])
            from langchain_core.messages import AIMessage
            return {"messages": [AIMessage(content="Day la cau tra loi.")]}

        mock_mcp_client = MagicMock()
        mock_mcp_client.get_tools = MagicMock(return_value=[])
        mock_mcp_ctx = MagicMock()
        mock_mcp_ctx.__aenter__ = AsyncMock(return_value=mock_mcp_client)
        mock_mcp_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("agents.orchestrator.MultiServerMCPClient", return_value=mock_mcp_ctx),
            patch(
                "agents.orchestrator.create_react_agent",
                return_value=MagicMock(ainvoke=capture_ainvoke),
            ),
        ):
            await orchestrator.chat(
                user_id=_FIXED_USER_ID,
                session_id=_FIXED_SESSION,
                user_message="Goi y do an vat di",
                health_profile=profile,
            )

        # First message must be SystemMessage containing the allergy
        from langchain_core.messages import SystemMessage
        system_msgs = [m for m in captured_messages if isinstance(m, SystemMessage)]
        assert system_msgs, "No SystemMessage was sent to the agent"
        assert "peanuts" in system_msgs[0].content

    @pytest.mark.asyncio
    async def test_clear_history_deletes_correct_key(self, orchestrator, mock_redis):
        """clear_history() must delete the scoped key chat:v1:{user_id}:{session_id}."""
        await orchestrator.clear_history(
            user_id=_FIXED_USER_ID,
            session_id=_FIXED_SESSION,
        )

        mock_redis.delete.assert_called_once()
        deleted_key: str = mock_redis.delete.call_args[0][0]
        assert str(_FIXED_USER_ID) in deleted_key
        assert _FIXED_SESSION in deleted_key
        assert deleted_key.startswith("chat:v1:")

    @pytest.mark.asyncio
    async def test_fallback_reply_when_no_ai_message(self, orchestrator):
        """If Gemini returns no AIMessage, a safe fallback string is returned."""
        mock_mcp_client = MagicMock()
        mock_mcp_client.get_tools = MagicMock(return_value=[])
        mock_mcp_ctx = MagicMock()
        mock_mcp_ctx.__aenter__ = AsyncMock(return_value=mock_mcp_client)
        mock_mcp_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("agents.orchestrator.MultiServerMCPClient", return_value=mock_mcp_ctx),
            patch(
                "agents.orchestrator.create_react_agent",
                return_value=MagicMock(
                    ainvoke=AsyncMock(return_value={"messages": []})
                ),
            ),
        ):
            reply = await orchestrator.chat(
                user_id=_FIXED_USER_ID,
                session_id=_FIXED_SESSION,
                user_message="?",
            )

        assert "Xin loi" in reply or "Xin l\u1ed7i" in reply
