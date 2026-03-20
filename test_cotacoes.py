"""Test cotacoes line and audience creation directly"""
from aicentralv2 import create_app
from aicentralv2.db import get_db

app = create_app()

with app.app_context():
    conn = get_db()

    # 1. Check table schemas
    print("=== cadu_cotacao_linhas schema ===")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'cadu_cotacao_linhas'
            ORDER BY ordinal_position
        """)
        for row in cur.fetchall():
            print(f"  {row['column_name']:30s} {row['data_type']:20s} nullable={row['is_nullable']} default={row['column_default']}")

    print("\n=== cadu_cotacao_audiencias schema ===")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'cadu_cotacao_audiencias'
            ORDER BY ordinal_position
        """)
        for row in cur.fetchall():
            print(f"  {row['column_name']:30s} {row['data_type']:20s} nullable={row['is_nullable']} default={row['column_default']}")

    # 2. Find a valid cotacao_id to test with
    print("\n=== Finding a test cotacao ===")
    with conn.cursor() as cur:
        cur.execute("SELECT id, numero_cotacao, status FROM cadu_cotacoes WHERE deleted_at IS NULL ORDER BY id DESC LIMIT 3")
        cotacoes = cur.fetchall()
        for c in cotacoes:
            print(f"  id={c['id']} numero={c['numero_cotacao']} status={c['status']}")

    if cotacoes:
        test_cotacao_id = cotacoes[0]['id']

        # 3. Test creating a line
        print(f"\n=== Testing criar_linha_cotacao (cotacao_id={test_cotacao_id}) ===")
        try:
            from aicentralv2 import db
            linha_id = db.criar_linha_cotacao(
                cotacao_id=test_cotacao_id,
                pedido_sugestao="Teste automatizado",
                segmentacao="Teste",
                plataforma="Google",
                investimento_bruto=1000.00
            )
            print(f"  SUCCESS: linha_id={linha_id}")
            # Clean up
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cadu_cotacao_linhas WHERE id = %s", (linha_id,))
            conn.commit()
            print("  Cleaned up test line")
        except Exception as e:
            conn.rollback()
            print(f"  FAILED: {e}")

        # 4. Test creating an audience
        print(f"\n=== Testing adicionar_audiencia_cotacao (cotacao_id={test_cotacao_id}) ===")
        try:
            aud_id = db.adicionar_audiencia_cotacao(
                cotacao_id=test_cotacao_id,
                audiencia_nome="Teste Audiencia",
                audiencia_id=None,
                audiencia_publico="100000",
                cpm_estimado=25.50,
                investimento_sugerido=5000.00,
                impressoes_estimadas=200000
            )
            print(f"  SUCCESS: audiencia_id={aud_id}")
            # Clean up
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cadu_cotacao_audiencias WHERE id = %s", (aud_id,))
            conn.commit()
            print("  Cleaned up test audience")
        except Exception as e:
            conn.rollback()
            print(f"  FAILED: {e}")
    else:
        print("  No cotacoes found to test with")

    print("\nDone!")
