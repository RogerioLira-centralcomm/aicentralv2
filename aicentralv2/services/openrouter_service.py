"""
Serviço OpenRouter para processamento de texto com Gemini
"""
import os
import json
import requests
from typing import Dict, Any

OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Prompt otimizado para transformar texto em FAQ estruturado
ANALYSIS_PROMPT = {
    "system": """Você é um especialista em análise e estruturação de documentos corporativos.
Sua tarefa é analisar textos e transformá-los em um FAQ abrangente e bem estruturado.

Regras de processamento:
1. Mantenha o contexto técnico e profissional
2. Identifique os principais conceitos e definições
3. Estruture em formato de perguntas e respostas claras
4. Agrupe informações relacionadas
5. Preserve termos técnicos importantes
6. Mantenha um tom profissional e objetivo
7. Inclua exemplos práticos quando relevante
8. Organize do mais geral para o mais específico
9. Mantenha referência a dados e métricas importantes
10. Inclua uma seção de conceitos-chave no início

Formato de saída:
# Conceitos-Chave
[Liste 3-5 conceitos fundamentais do texto]

# FAQ
Q: [Pergunta clara e direta]
A: [Resposta detalhada e estruturada]

[Continue com mais perguntas e respostas, organizadas por temas]""",
    "max_tokens": 4000,
    "temperature": 0.3
}

def process_text_with_gemini(text: str) -> Dict[str, Any]:
    """
    Processa um texto usando o modelo Gemini através do OpenRouter.
    
    Args:
        text: Texto a ser processado
        
    Returns:
        Dict com o texto processado e metadados
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://centralcomm.media",
        "X-Title": "CentralComm AI"
    }
    
    messages = [
        {
            "role": "system",
            "content": ANALYSIS_PROMPT["system"]
        },
        {
            "role": "user",
            "content": f"Analise e estruture o seguinte texto em formato FAQ:\n\n{text}"
        }
    ]
    
    payload = {
        "model": "google/gemini-pro",  # Usando Gemini Pro para melhor processamento de texto
        "messages": messages,
        "max_tokens": ANALYSIS_PROMPT["max_tokens"],
        "temperature": ANALYSIS_PROMPT["temperature"]
    }
    
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=180  # Timeout aumentado para textos longos
        )
        
        response.raise_for_status()
        result = response.json()
        
        processed_text = result['choices'][0]['message']['content']
        
        return {
            'success': True,
            'processed_text': processed_text,
            'metadata': {
                'model': result.get('model', 'google/gemini-pro'),
                'usage': result.get('usage', {}),
                'processing_stats': {
                    'tokens': result.get('usage', {}).get('total_tokens', 0)
                }
            }
        }
        
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': str(e),
            'processed_text': text,  # Retorna texto original em caso de erro
            'metadata': {
                'error_details': str(e)
            }
        }

# Função auxiliar para processar textos muito longos em chunks
def process_large_text(text: str, max_chunk_size: int = 8000) -> str:
    """
    Processa textos longos dividindo em chunks e mantendo contexto.
    
    Args:
        text: Texto completo
        max_chunk_size: Tamanho máximo de cada chunk
        
    Returns:
        Texto processado completo
    """
    if len(text) <= max_chunk_size:
        result = process_text_with_gemini(text)
        return result['processed_text'] if result['success'] else text
    
    # Dividir em chunks preservando parágrafos
    chunks = []
    current_chunk = []
    current_size = 0
    
    for paragraph in text.split('\n\n'):
        if current_size + len(paragraph) > max_chunk_size:
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
        
        current_chunk.append(paragraph)
        current_size += len(paragraph) + 2  # +2 para \n\n
    
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    # Processar cada chunk
    processed_chunks = []
    for i, chunk in enumerate(chunks):
        context = f"Este é o segmento {i+1} de {len(chunks)} do documento. "
        chunk_with_context = context + chunk
        
        result = process_text_with_gemini(chunk_with_context)
        if result['success']:
            processed_chunks.append(result['processed_text'])
        else:
            processed_chunks.append(chunk)
    
    # Combinar resultados
    return "\n\n# Próxima Seção\n\n".join(processed_chunks)