"""Add foreign key to Script model

Revision ID: 4b2caad877ec
Revises: d5fd1c89e6e3
Create Date: 2024-09-05 09:43:24.863238

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b2caad877ec'
down_revision: Union[str, None] = 'd5fd1c89e6e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('scripts') as batch_op:
        batch_op.add_column(sa.Column('podcast_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_scripts_podcast_id', 'podcasts', ['podcast_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('scripts') as batch_op:
        batch_op.drop_constraint('fk_scripts_podcast_id', type_='foreignkey')
        batch_op.drop_column('podcast_id')
