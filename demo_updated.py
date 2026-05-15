import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, String, func
from datetime import datetime, timezone

engine = create_async_engine(
    "postgresql+asyncpg://datamind:datamind@100.92.47.128:5432/datamind",
    echo=True,
)

class Base(DeclarativeBase): pass

class TestA(Base):
    __tablename__ = "test_a"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

class TestB(Base):
    __tablename__ = "test_b"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )

async def runner():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)  # 建表

    async with AsyncSession(engine, expire_on_commit=False) as s:
        a = TestA(name="a"); b = TestB(name="b")
        s.add_all([a, b]); await s.commit()
        t1_a = a.updated_at; t1_b = b.updated_at

        await asyncio.sleep(1)
        a.name = "a2"; b.name = "b2"
        await s.commit()

        await s.refresh(a)
        await s.refresh(b)

        print(f"A updated: {a.updated_at > t1_a}")
        print(f"B updated: {b.updated_at > t1_b}")

if __name__ == "__main__":
    asyncio.run(runner())