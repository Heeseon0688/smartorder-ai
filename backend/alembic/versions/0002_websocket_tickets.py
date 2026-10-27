"""Short-lived, single-use WebSocket authentication tickets."""
from alembic import op
import sqlalchemy as sa
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('websocket_tickets',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('session_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False))
    op.create_index('ix_websocket_tickets_session_hash','websocket_tickets',['session_hash'])
    op.create_index('ix_websocket_tickets_expires_at','websocket_tickets',['expires_at'])

def downgrade():
    op.drop_table('websocket_tickets')
