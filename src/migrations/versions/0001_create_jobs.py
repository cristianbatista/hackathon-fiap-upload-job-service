"""create jobs table

Revision ID: 0001
Revises:
Create Date: 2026-03-13
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE jobstatus AS ENUM ('PENDING', 'PROCESSING', 'DONE', 'ERROR');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL,
            filename VARCHAR(512) NOT NULL,
            file_size_bytes INTEGER NOT NULL,
            status jobstatus NOT NULL DEFAULT 'PENDING',
            error_message TEXT,
            result_path VARCHAR(1024),
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_user_id ON jobs (user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_jobs_user_id")
    op.execute("DROP TABLE IF EXISTS jobs")
    op.execute("DROP TYPE IF EXISTS jobstatus")
