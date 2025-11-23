#!/usr/bin/env python3
"""
Script de diagnóstico para verificar schema da tabela cadu_client_plans
Execute no servidor de produção para identificar diferenças de schema
"""

import os
import sys
from pathlib import Path

# Adicionar o diretório raiz ao PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from aicentralv2.db import get_db

def verificar_schema_cadu_client_plans():
    """Verifica e exibe o schema da tabela cadu_client_plans"""
    conn = get_db()
    
    try:
        with conn.cursor() as cursor:
            # Obter informações das colunas
            cursor.execute("""
                SELECT 
                    column_name, 
                    data_type, 
                    is_nullable,
                    column_default,
                    character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = 'cadu_client_plans'
                ORDER BY ordinal_position
            """)
            
            colunas = cursor.fetchall()
            
            print("\n" + "="*80)
            print("SCHEMA DA TABELA cadu_client_plans")
            print("="*80 + "\n")
            
            print(f"{'Coluna':<30} {'Tipo':<20} {'Nullable':<10} {'Default'}")
            print("-"*80)
            
            for col in colunas:
                col_name = col['column_name']
                col_type = col['data_type']
                if col['character_maximum_length']:
                    col_type += f"({col['character_maximum_length']})"
                nullable = 'YES' if col['is_nullable'] == 'YES' else 'NO'
                default = col['column_default'] or ''
                if len(default) > 30:
                    default = default[:27] + '...'
                
                print(f"{col_name:<30} {col_type:<20} {nullable:<10} {default}")
            
            print("\n" + "="*80)
            
            # Verificar constraints
            cursor.execute("""
                SELECT 
                    conname AS constraint_name,
                    contype AS constraint_type,
                    pg_get_constraintdef(c.oid) AS constraint_definition
                FROM pg_constraint c
                JOIN pg_namespace n ON n.oid = c.connamespace
                JOIN pg_class cl ON cl.oid = c.conrelid
                WHERE cl.relname = 'cadu_client_plans'
                  AND n.nspname = 'public'
            """)
            
            constraints = cursor.fetchall()
            
            print("\nCONSTRAINTS:")
            print("-"*80)
            for cons in constraints:
                tipo_map = {
                    'p': 'PRIMARY KEY',
                    'f': 'FOREIGN KEY',
                    'u': 'UNIQUE',
                    'c': 'CHECK'
                }
                tipo = tipo_map.get(cons['constraint_type'], cons['constraint_type'])
                print(f"{cons['constraint_name']:<30} {tipo:<15} {cons['constraint_definition']}")
            
            # Verificar dados
            cursor.execute("SELECT COUNT(*) as total FROM cadu_client_plans")
            total = cursor.fetchone()['total']
            
            print("\n" + "="*80)
            print(f"Total de registros: {total}")
            
            if total > 0:
                cursor.execute("""
                    SELECT plan_type, plan_status, COUNT(*) as qtd 
                    FROM cadu_client_plans 
                    GROUP BY plan_type, plan_status
                    ORDER BY plan_type, plan_status
                """)
                
                stats = cursor.fetchall()
                print("\nDistribuição de planos:")
                print(f"{'Tipo':<30} {'Status':<15} {'Quantidade'}")
                print("-"*80)
                for stat in stats:
                    print(f"{stat['plan_type']:<30} {stat['plan_status']:<15} {stat['qtd']}")
            
            print("\n" + "="*80)
            
            # Verificações específicas
            print("\nVERIFICAÇÕES:")
            print("-"*80)
            
            col_names = [col['column_name'] for col in colunas]
            
            # Verificar nome da PK
            if 'id_plan' in col_names:
                print("✓ Coluna PK: id_plan (CORRETO)")
            elif 'id' in col_names:
                print("✗ Coluna PK: id (DEVE SER id_plan)")
                print("  Executar: ALTER TABLE cadu_client_plans RENAME COLUMN id TO id_plan;")
            else:
                print("✗ Coluna PK não encontrada!")
            
            # Verificar colunas de data
            data_cols_required = ['plan_start_date', 'plan_end_date', 'valid_from', 'valid_until']
            data_cols_missing = [col for col in data_cols_required if col not in col_names]
            
            if not data_cols_missing:
                print("✓ Todas as colunas de data presentes")
            else:
                print(f"✗ Colunas de data faltando: {', '.join(data_cols_missing)}")
            
            # Verificar features JSONB
            features_col = next((col for col in colunas if col['column_name'] == 'features'), None)
            if features_col:
                if features_col['data_type'] == 'jsonb':
                    print("✓ Coluna features é JSONB")
                else:
                    print(f"✗ Coluna features é {features_col['data_type']}, deveria ser JSONB")
            else:
                print("✗ Coluna features não encontrada")
            
            print("\n" + "="*80 + "\n")
            
    except Exception as e:
        print(f"\n❌ ERRO: {str(e)}\n")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    print("\n🔍 Verificando schema da tabela cadu_client_plans...\n")
    verificar_schema_cadu_client_plans()
