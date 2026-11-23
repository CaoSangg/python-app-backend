"""Read migration and TLS evidence through the app identity without printing the DSN."""

import argparse
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


async def verify(database: str, revision: str) -> bool:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool, hide_parameters=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            identity = (await connection.execute(text("""
                SELECT current_database(),
                       to_regclass('public.song') IS NOT NULL,
                       (SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid())
            """))).one()
            versions = (await connection.execute(text("SELECT version_num FROM public.alembic_version"))).scalars().all()
            return identity == (database, True, True) and versions == [revision]
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", help="Expected database name from the approved handover")
    parser.add_argument("revision", help="Expected Alembic head from the release source")
    args = parser.parse_args()
    try:
        if asyncio.run(asyncio.wait_for(verify(args.database, args.revision), timeout=15)):
            print("Database PASS: expected name, TLS, public.song and Alembic head")
            return 0
    except Exception:
        print("Database check failed: connection or read-only inspection failed", file=sys.stderr)
        return 1
    print("Database check failed: database, TLS, table or Alembic revision mismatch", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
