import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import TypeVar
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bitenary_mcp.domain.entities import (
    MCPPrincipal,
    MCPUsageOutcome,
)
from bitenary_mcp.infrastructure.sqlalchemy_mcp import (
    SqlAlchemyMCPAuditRepository,
)


ResultT = TypeVar("ResultT")
logger = logging.getLogger(__name__)


class MCPInvocationAuditor:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def invoke(
        self,
        *,
        principal: MCPPrincipal,
        tool_name: str,
        operation: Callable[[], Awaitable[ResultT]],
    ) -> ResultT:
        request_id = uuid4()
        invoked_at = datetime.now(UTC)
        started = perf_counter()

        async with self._session_factory() as session:
            repository = SqlAlchemyMCPAuditRepository(session)
            await repository.start_invocation(
                request_id=request_id,
                client_id=principal.client_id,
                tool_name=tool_name,
                invoked_at=invoked_at,
            )

        try:
            result = await operation()
        except Exception:
            await self._finish(
                request_id=request_id,
                outcome=MCPUsageOutcome.FAILED,
                started=started,
                error_code="TOOL_EXECUTION_FAILED",
            )
            raise

        await self._finish(
            request_id=request_id,
            outcome=MCPUsageOutcome.SUCCEEDED,
            started=started,
            error_code=None,
        )
        return result

    async def _finish(
        self,
        *,
        request_id: UUID,
        outcome: MCPUsageOutcome,
        started: float,
        error_code: str | None,
    ) -> None:
        completed_at = datetime.now(UTC)
        latency_ms = max(0, round((perf_counter() - started) * 1000))
        try:
            async with self._session_factory() as session:
                repository = SqlAlchemyMCPAuditRepository(session)
                await repository.finish_invocation(
                    request_id=request_id,
                    outcome=outcome,
                    completed_at=completed_at,
                    latency_ms=latency_ms,
                    error_code=error_code,
                )
        except Exception:
            # The PENDING row created before execution remains as evidence that
            # final audit persistence failed. Never include request payloads.
            logger.exception("Could not finalize MCP usage audit")
