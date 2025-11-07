from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'cadu_categorias_audiencia',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('categoria', sa.String(100), nullable=False),
        sa.Column('subcategoria', sa.String(100)),
        sa.Column('nome_exibicao', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(200), nullable=False),
        sa.Column('descricao', sa.Text()),
        sa.Column('icone', sa.String(100)),
        sa.Column('cor_hex', sa.String(7)),
        sa.Column('ordem_exibicao', sa.Integer(), server_default='0'),
        sa.Column('is_active', sa.Boolean(), server_default=sa.sql.expression.true()),
        sa.Column('is_featured', sa.Boolean(), server_default=sa.sql.expression.false()),
        sa.Column('total_audiencias', sa.Integer(), server_default='0'),
        sa.Column('meta_titulo', sa.String(200)),
        sa.Column('meta_descricao', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table('cadu_categorias_audiencia')
