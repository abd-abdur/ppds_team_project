"""Add outfit_clothings association table and update Outfit model

Revision ID: 4fa8d6374383
Revises: f7f9d7857346
Create Date: 2024-11-12 18:17:25.172180

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '4fa8d6374383'
down_revision: Union[str, None] = 'f7f9d7857346'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('outfit_clothings',
    sa.Column('outfit_id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['wardrobe_items.item_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['outfit_id'], ['outfits.outfit_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('outfit_id', 'item_id')
    )
    op.drop_column('outfits', 'clothings')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('outfits', sa.Column('clothings', mysql.JSON(), nullable=False))
    op.drop_table('outfit_clothings')
    # ### end Alembic commands ###