from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import Boolean, Index, String, and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from ingredients.domain.entities import IngredientMaster

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).parent.parent.parent / "data" / "cleaned_ingredients.json"


# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------

class IngredientMasterModel(Base):
    __tablename__ = "ingredient_master"

    ingredient_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    variant: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    __table_args__ = (
        # Full-text search index on name for fast ILIKE queries.
        Index("ix_ingredient_master_name_trgm", "name", postgresql_using="gin",
              postgresql_ops={"name": "gin_trgm_ops"}),
    )


def _to_domain(model: IngredientMasterModel) -> IngredientMaster:
    return IngredientMaster(
        ingredient_id=model.ingredient_id,
        name=model.name,
        variant=model.variant,
        category=model.category,
        is_default=model.is_default,
    )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class SqlAlchemyIngredientRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self,
        *,
        q: str | None = None,
        category: str | None = None,
        only_default: bool = True,
        page: int = 1,
        size: int = 20,
    ) -> list[IngredientMaster]:
        stmt = select(IngredientMasterModel)

        normalized_query = " ".join(q.casefold().split()) if q else ""

        if only_default:
            stmt = stmt.where(IngredientMasterModel.is_default.is_(True))

        if category:
            stmt = stmt.where(
                func.lower(IngredientMasterModel.category) == category.lower()
            )

        if normalized_query:
            name = func.lower(IngredientMasterModel.name)
            variant = func.lower(IngredientMasterModel.variant)
            searchable_text = name + " " + variant
            phrase_pattern = f"%{normalized_query}%"
            token_matches = [
                searchable_text.like(f"%{token}%")
                for token in normalized_query.split()
            ]
            stmt = stmt.where(
                or_(
                    name.like(phrase_pattern),
                    variant.like(phrase_pattern),
                    and_(*token_matches),
                )
            )
            relevance = case(
                (name == normalized_query, 0),
                (name.like(f"{normalized_query}%"), 1),
                (name.like(phrase_pattern), 2),
                (variant.like(f"{normalized_query}%"), 3),
                (variant.like(phrase_pattern), 4),
                else_=5,
            )
            stmt = stmt.order_by(
                relevance,
                IngredientMasterModel.is_default.desc(),
                func.length(IngredientMasterModel.name),
                IngredientMasterModel.name,
                func.length(IngredientMasterModel.variant),
                IngredientMasterModel.variant,
            )
        else:
            stmt = stmt.order_by(
                IngredientMasterModel.name,
                IngredientMasterModel.is_default.desc(),
                IngredientMasterModel.variant,
            )
        stmt = stmt.offset((page - 1) * size).limit(size)

        result = await self._session.execute(stmt)
        return [_to_domain(m) for m in result.scalars().all()]

    async def get_categories(self) -> list[str]:
        stmt = (
            select(IngredientMasterModel.category)
            .distinct()
            .order_by(IngredientMasterModel.category)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(IngredientMasterModel)
        )
        return result.scalar_one()

    async def seed_from_json(self, filepath: Path = _DATA_FILE) -> int:
        """Idempotent seed: only runs when the table is empty."""
        existing = await self.count()
        if existing > 0:
            logger.info(
                "ingredient_master already seeded (%d rows). Skipping.", existing
            )
            return 0

        with open(filepath, encoding="utf-8") as f:
            records: list[dict] = json.load(f)

        batch_size = 500
        inserted = 0
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            self._session.add_all(
                IngredientMasterModel(
                    ingredient_id=UUID(rec["id"]),
                    name=rec["name"],
                    variant=rec.get("variant") or "",
                    category=rec["category"],
                    is_default=rec["is_default"],
                )
                for rec in batch
            )
            await self._session.commit()
            inserted += len(batch)

        logger.info("Seeded %d ingredients into ingredient_master.", inserted)
        return inserted
