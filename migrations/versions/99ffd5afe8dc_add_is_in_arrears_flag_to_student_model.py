"""Add is_in_arrears flag to Student model

Revision ID: 99ffd5afe8dc
Revises: efa85ce02ec0
Create Date: 2025-05-09 09:43:01.908919

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '99ffd5afe8dc'
down_revision = 'efa85ce02ec0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
#    with op.batch_alter_table('students', schema=None) as batch_op:
#        batch_op.add_column(sa.Column('is_in_arrears', sa.Boolean(), nullable=False))
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_in_arrears', sa.Boolean(), nullable=False, server_default=sa.false()))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
#    with op.batch_alter_table('students', schema=None) as batch_op:
#        batch_op.drop_column('is_in_arrears')
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('is_in_arrears')
    # ### end Alembic commands ###
