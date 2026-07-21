from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, String, func, select
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from identity.domain.entities import User, UserStatus
from identity.repository.users import UserRepository

# SQLAlchemy ORM model for users table
class UserModel(Base):  
    __tablename__ = "users"

    user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    authentik_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"),
        nullable=False,
        default=UserStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def to_domain(model: UserModel) -> User:
    return User(
        user_id=model.user_id,
        authentik_sub=model.authentik_sub,
        username=model.username,
        email=model.email,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        if model is None:
            return None
        return to_domain(model)

    async def get_by_authentik_sub(self, authentik_sub: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.authentik_sub == authentik_sub)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return to_domain(model)

    async def upsert_from_authentik_claims(
        self,
        *,
        authentik_sub: str,
        username: str,
        email: str | None,
    ) -> User:
        result = await self._session.execute(
            select(UserModel).where(UserModel.authentik_sub == authentik_sub)
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = UserModel(
                authentik_sub=authentik_sub,
                username=username,
                email=email,
                status=UserStatus.ACTIVE,
            )
            self._session.add(model)
        else:
            model.username = username
            model.email = email

        await self._session.commit()
        await self._session.refresh(model)
        return to_domain(model)
