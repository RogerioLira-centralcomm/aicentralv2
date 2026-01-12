-- Migration: Adicionar novos campos para cadu_cotacao_linhas e cadu_cotacoes
-- Data: 2024
-- Descrição: Adiciona campos para praça, valores de tabela, desconto e investimento líquido

-- ==================== CAMPOS PARA CADU_COTACAO_LINHAS ====================

-- Adicionar campo praça (localização geográfica)
ALTER TABLE cadu_cotacao_linhas 
ADD COLUMN IF NOT EXISTS praca VARCHAR(100);

-- Adicionar campo valor unitário de tabela
ALTER TABLE cadu_cotacao_linhas 
ADD COLUMN IF NOT EXISTS valor_unitario_tabela DECIMAL(15, 4) DEFAULT 0;

-- Adicionar campo percentual de desconto
ALTER TABLE cadu_cotacao_linhas 
ADD COLUMN IF NOT EXISTS desconto_percentual DECIMAL(5, 2) DEFAULT 0;

-- Adicionar campo valor unitário negociado (após desconto)
ALTER TABLE cadu_cotacao_linhas 
ADD COLUMN IF NOT EXISTS valor_unitario_negociado DECIMAL(15, 4) DEFAULT 0;

-- Adicionar campo investimento líquido
ALTER TABLE cadu_cotacao_linhas 
ADD COLUMN IF NOT EXISTS investimento_liquido DECIMAL(15, 2) DEFAULT 0;

-- Comentários para documentação
COMMENT ON COLUMN cadu_cotacao_linhas.praca IS 'Praça/região geográfica da linha (Ex: Nacional, SP, RJ)';
COMMENT ON COLUMN cadu_cotacao_linhas.valor_unitario_tabela IS 'Valor unitário original de tabela antes do desconto';
COMMENT ON COLUMN cadu_cotacao_linhas.desconto_percentual IS 'Percentual de desconto aplicado (0-100)';
COMMENT ON COLUMN cadu_cotacao_linhas.valor_unitario_negociado IS 'Valor unitário após aplicação do desconto';
COMMENT ON COLUMN cadu_cotacao_linhas.investimento_liquido IS 'Investimento líquido calculado com base no percentual do cliente';

-- ==================== CAMPOS PARA CADU_COTACOES ====================

-- Adicionar campo desconto total da proposta
ALTER TABLE cadu_cotacoes 
ADD COLUMN IF NOT EXISTS desconto_total DECIMAL(15, 2) DEFAULT 0;

-- Adicionar campo condições comerciais
ALTER TABLE cadu_cotacoes 
ADD COLUMN IF NOT EXISTS condicoes_comerciais TEXT;

-- Comentários para documentação
COMMENT ON COLUMN cadu_cotacoes.desconto_total IS 'Desconto total aplicado na proposta (em reais)';
COMMENT ON COLUMN cadu_cotacoes.condicoes_comerciais IS 'Condições comerciais da proposta (texto livre)';
