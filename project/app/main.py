import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Request, Response, status
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import DATABASE_ERRORS, get_session, lifespan
from app.models import MAX_DB_INTEGER, Song, SongCreate, SongRead

app = FastAPI(title="Song Management API", lifespan=lifespan)
logger = logging.getLogger(__name__)

SongID = Annotated[int, Path(gt=0, le=MAX_DB_INTEGER)]
Session = Annotated[AsyncSession, Depends(get_session, scope="function")]
SONG_NOT_FOUND = {404: {"description": "Song not found"}}
songs = APIRouter(
    prefix="/songs",
    responses={
        500: {"description": "Database operation failed"},
        503: {"description": "Database unavailable"},
    },
)


@app.get("/ping")
async def pong():
    return {"ping": "pong!"}


@app.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", responses={503: {"description": "Database unavailable"}})
async def readiness(request: Request) -> dict[str, str]:
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        async with asyncio.timeout(2):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except DATABASE_ERRORS as exc:
        logger.warning("Database readiness check failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Database unavailable") from None

    return {"status": "ok"}


async def find_song(song_id: int, session: AsyncSession) -> Song:
    song = await session.get(Song, song_id)
    if song is None:
        raise HTTPException(status_code=404, detail="Song not found")
    return song


@songs.get("", response_model=list[SongRead])
async def get_songs(session: Session):
    result = await session.exec(select(Song).order_by(Song.id))
    return result.all()


@songs.post("", response_model=SongRead, status_code=status.HTTP_201_CREATED)
async def add_song(payload: SongCreate, session: Session):
    song = Song.model_validate(payload)
    session.add(song)
    await session.commit()
    return song


@songs.get("/{song_id}", response_model=SongRead, responses=SONG_NOT_FOUND)
async def get_song(song_id: SongID, session: Session):
    return await find_song(song_id, session)


@songs.put("/{song_id}", response_model=SongRead, responses=SONG_NOT_FOUND)
async def update_song(song_id: SongID, payload: SongCreate, session: Session):
    song = await find_song(song_id, session)
    song.sqlmodel_update(payload.model_dump())
    await session.commit()
    return song


@songs.delete("/{song_id}", status_code=status.HTTP_204_NO_CONTENT, responses=SONG_NOT_FOUND)
async def delete_song(song_id: SongID, session: Session):
    song = await find_song(song_id, session)
    await session.delete(song)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


app.include_router(songs)
