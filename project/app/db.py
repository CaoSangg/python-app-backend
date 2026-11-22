import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from asyncpg import InterfaceError, PostgresError
from fastapi import FastAPI, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession


logger = logging.getLogger(__name__)
DATABASE_ERRORS = (SQLAlchemyError, PostgresError, InterfaceError, OSError)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    database_url = os.getenv("DATABASE_URL")
    app.state.engine = None
    app.state.session_factory = None
    if not database_url:
        logger.warning("DATABASE_URL is not configured")
        yield
        return

    engine = create_async_engine(database_url, pool_pre_ping=True, hide_parameters=True)
    app.state.engine = engine
    app.state.session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        yield
    finally:
        await engine.dispose()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.session_factory
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        async with session_factory() as session:
            yield session
    except DATABASE_ERRORS as exc:
        logger.error("Database operation failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Database operation failed") from None
