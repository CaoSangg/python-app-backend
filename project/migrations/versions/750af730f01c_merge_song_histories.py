"""Merge upstream revisions that migrated the same song table."""

from alembic import op
from alembic.util import CommandError


revision = "750af730f01c"
down_revision = ("53754b2c08a4", "f68b489cdeb0")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Both histories share the table and the year index. Remove the legacy-only indexes.
    for column in ("artist", "id", "name"):
        op.drop_index(f"ix_song_{column}", table_name="song", if_exists=True)


def downgrade() -> None:
    raise CommandError("Downgrading through the merge can delete shared song data")
