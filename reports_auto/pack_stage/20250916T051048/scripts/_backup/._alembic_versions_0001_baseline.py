from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "actions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("idem", sa.String(128), index=True),
        sa.Column("status", sa.String(32), index=True, nullable=False, server_default="queued"),
        sa.Column("payload", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("idem", sa.String(128)),
        sa.Column("level", sa.String(16), index=True),
        sa.Column("message", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("idem", sa.String(128)),
        sa.Column("data", sa.JSON()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "dead_letters",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("reason", sa.Text()),
        sa.Column("payload", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )

def downgrade():
    for t in ("dead_letters","tickets","alerts","actions"):
        op.drop_table(t)
