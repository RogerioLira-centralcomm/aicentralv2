#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para executar queries no banco de dados PostgreSQL
"""
import psycopg2
from psycopg2.extras import RealDictCursor

try:
    # Credenciais de conexão
    conn = psycopg2.connect(
        host='212.85.13.233',
        port=123,
        database='centralp',
        user='postgres',
        password='nova_senha'
    )

    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Query 1
    print('=' * 80)
    print('QUERY 1: SELECT display FROM tbl_setor WHERE status = true ORDER BY display;')
    print('=' * 80)
    cursor.execute('SELECT display FROM tbl_setor WHERE status = true ORDER BY display;')
    rows = cursor.fetchall()
    if rows:
        for i, row in enumerate(rows, 1):
            print(f"{i}. {row['display']}")
    else:
        print('Nenhum resultado encontrado.')
    print()

    # Query 2
    print('=' * 80)
    print('QUERY 2: SELECT descricao FROM tbl_cargo_contato WHERE status = true ORDER BY descricao LIMIT 20;')
    print('=' * 80)
    cursor.execute('SELECT descricao FROM tbl_cargo_contato WHERE status = true ORDER BY descricao LIMIT 20;')
    rows = cursor.fetchall()
    if rows:
        for i, row in enumerate(rows, 1):
            print(f"{i}. {row['descricao']}")
    else:
        print('Nenhum resultado encontrado.')
    print()

    # Query 3
    print('=' * 80)
    print('QUERY 3: Contatos de Clientes (filtro: centralcomm)')
    print('=' * 80)
    cursor.execute('''
        SELECT c.nome_completo, cli.nome_fantasia, car.descricao, s.display 
        FROM tbl_contato_cliente c 
        LEFT JOIN tbl_cliente cli ON c.pk_id_tbl_cliente = cli.id_cliente 
        LEFT JOIN tbl_cargo_contato car ON c.pk_id_tbl_cargo = car.id_cargo_contato 
        LEFT JOIN tbl_setor s ON c.pk_id_tbl_setor = s.id_setor 
        WHERE cli.nome_fantasia ILIKE '%centralcomm%' AND c.status = true 
        ORDER BY c.nome_completo LIMIT 10;
    ''')
    rows = cursor.fetchall()
    if rows:
        print(f'Total: {len(rows)} registros\n')
        print(f"{'Nome Completo':<30} | {'Nome Fantasia':<25} | {'Cargo':<25} | {'Setor':<20}")
        print("-" * 120)
        for row in rows:
            nome = row['nome_completo'] or 'N/A'
            cliente = row['nome_fantasia'] or 'N/A'
            cargo = row['descricao'] or 'N/A'
            setor = row['display'] or 'N/A'
            print(f"{nome:<30} | {cliente:<25} | {cargo:<25} | {setor:<20}")
    else:
        print('Nenhum resultado encontrado.')

    cursor.close()
    conn.close()
    print('\n✓ Conexão fechada com sucesso.')

except psycopg2.OperationalError as e:
    print(f'❌ Erro de conexão: {e}')
except Exception as e:
    print(f'❌ Erro: {e}')
