"""empty message

Revision ID: 1cb83c2a2474
Revises: 21a2080a1528
Create Date: 2024-04-28 12:52:31.174639

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1cb83c2a2474'
down_revision = '21a2080a1528'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('booking', schema=None) as batch_op:
        batch_op.create_unique_constraint('unique_booking', ['court_id', 'booking_date', 'start_time', 'end_time'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('booking', schema=None) as batch_op:
        batch_op.drop_constraint('unique_booking', type_='unique')

    # ### end Alembic commands ###
