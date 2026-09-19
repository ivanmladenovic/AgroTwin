"""map knowledge manuals to protection, nutrition, general

Revision ID: d5e6f70819a0
Revises: c4d5e6f70819
Create Date: 2026-09-14 13:29:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d5e6f70819a0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f70819"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE documents
        SET category = 'plant_protection'
        WHERE category IN ('disease_guide', 'pest_guide')
        """
    )
    op.execute(
        """
        UPDATE documents
        SET category = 'other'
        WHERE category IN ('manual', 'best_practice')
        """
    )
    op.execute(
        """
        UPDATE documents
        SET category = 'nutrition_guide'
        WHERE title IN (
            'Politika ishrane i zaštite bilja',
            'Nutrition and plant protection policy'
        )
        """
    )


def downgrade() -> None:
    pass
