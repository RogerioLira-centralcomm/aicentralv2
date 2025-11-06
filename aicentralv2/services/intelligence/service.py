import os
import json
import logging
import requests
from ...db import get_db
from aicentralv2.config import PINECONE_CONFIG

# Logger do módulo
logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

class IntelligenceService:
    def __init__(self):
        """Inicializa dependências de forma preguiçosa (lazy) para evitar erros de import no startup.

        As bibliotecas pesadas (pinecone, sentence-transformers, numpy, PyPDF2) são importadas
        apenas quando necessárias. Assim a aplicação sobe mesmo em ambientes sem essas libs.
        """
        self._pinecone = None
        self._pinecone_cfg = PINECONE_CONFIG
        self.index = None
        self.embedding_model = None

        # Tenta inicializar Pinecone
        try:
            import pinecone  # type: ignore
            pinecone.init(
                api_key=self._pinecone_cfg.get('api_key'),
                environment=self._pinecone_cfg.get('environment'),
                host=self._pinecone_cfg.get('host')
            )
            self._pinecone = pinecone
            self.index = pinecone.Index(self._pinecone_cfg.get('index_name'))
        except Exception as e:
            logger.warning(f"Pinecone não inicializado: {e}")

        # Tenta inicializar o modelo de embeddings
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.warning(f"SentenceTransformer indisponível: {e}")

    def process_document(self, file_path, title, requires_cadu_format=False):
        """
        Processa um documento e envia para o Pinecone.
        """
        db = get_db()
        cursor = db.cursor()
        
        # Criar registro do documento
        cursor.execute("""
            INSERT INTO intelligence_documents 
                (title, document_type, requires_cadu_format, status, metadata)
            VALUES (%s, %s, %s, 'processing', %s)
            RETURNING id
        """, (
            title,
            os.path.splitext(file_path)[1][1:],
            requires_cadu_format,
            {'source': 'upload'}
        ))
        
        document_id = cursor.fetchone()[0]
        db.commit()
        
        try:
            # Extrair texto do documento
            if file_path.endswith('.pdf'):
                text = self._extract_text_from_pdf(file_path)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            
            # Se não precisa do formato CADU, processar com Gemini
            if not requires_cadu_format:
                text = self._process_with_gemini(text)
            
            # Verifica dependências críticas antes de prosseguir
            if self.index is None:
                raise RuntimeError("Pinecone não está configurado nesta instância.")
            if self.embedding_model is None:
                raise RuntimeError("Modelo de embeddings (sentence-transformers) não está disponível.")

            # Dividir em chunks
            chunks = self._create_chunks(text)
            
            # Processar e enviar chunks para Pinecone
            pinecone_ids = []
            for i, chunk in enumerate(chunks):
                # Criar embedding (implemente a função conforme necessário)
                embedding = self._create_embedding(chunk)
                
                # Gerar ID único para o chunk
                chunk_id = f"doc_{document_id}_chunk_{i}"
                
                # Inserir no Pinecone
                self.index.upsert([(chunk_id, embedding, {
                    'document_id': document_id,
                    'chunk_number': i,
                    'text': chunk,
                    'title': title
                })])
                
                pinecone_ids.append(chunk_id)
                
                # Atualizar status
                self._update_processing_status(document_id, {
                    'status': 'processing',
                    'chunks_processed': i + 1,
                    'total_chunks': len(chunks)
                })
            
            # Finalizar processamento
            cursor.execute("""
                UPDATE intelligence_documents
                SET status = 'completed',
                    pinecone_ids = %s,
                    processed_text = %s
                WHERE id = %s
            """, (pinecone_ids, text, document_id))
            
            db.commit()
            
            return {
                'id': document_id,
                'status': 'completed',
                'pinecone_ids': pinecone_ids
            }
            
        except Exception as e:
            cursor.execute("""
                UPDATE intelligence_documents
                SET status = 'error',
                    metadata = jsonb_set(
                        metadata,
                        '{error}',
                        %s::jsonb
                    )
                WHERE id = %s
            """, (json.dumps({'message': str(e)}), document_id))
            
            db.commit()
            raise

    def _extract_text_from_pdf(self, file_path):
        """Extrai texto de um arquivo PDF"""
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception as e:
            raise RuntimeError(f"Dependência PyPDF2 indisponível: {e}")
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text

    def _process_with_gemini(self, text):
        """Processa o texto com Gemini para criar FAQ"""
        from ..openrouter_service import process_large_text
        
        try:
            # Processa o texto, dividindo em chunks se necessário
            processed_text = process_large_text(text)
            return processed_text
        except Exception as e:
            logger.error(f"Erro no processamento Gemini: {e}")
            # Em caso de erro, retorna o texto original
            return text

    def _create_chunks(self, text, chunk_size=1000, overlap=100):
        """Divide o texto em chunks com sobreposição"""
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            
            if end > text_length:
                end = text_length
            else:
                # Procura o próximo espaço em branco para não cortar palavras
                while end < text_length and text[end] not in [' ', '\n']:
                    end += 1
            
            chunk = text[start:end]
            chunks.append(chunk)
            
            start = end - overlap
            
        return chunks

    def _create_embedding(self, text):
        """
        Cria embedding para um texto usando o modelo all-MiniLM-L6-v2.
        Este modelo produz embeddings de 384 dimensões que são então mapeados para 512
        através de padding com zeros para compatibilidade com o Pinecone.
        """
        if self.embedding_model is None:
            raise RuntimeError("Modelo de embeddings indisponível. Instale sentence-transformers.")
        # Criar embedding base
        embedding = self.embedding_model.encode(text)

        # Padding para 512 dimensões
        try:
            import numpy as np  # type: ignore
        except Exception as e:
            raise RuntimeError(f"Dependência numpy indisponível: {e}")
        padded_embedding = np.zeros(512, dtype=float)
        # Garante que comprimento não exceda 512
        end = min(384, len(embedding))
        padded_embedding[:end] = embedding[:end]
        return padded_embedding.tolist()

    def _update_processing_status(self, document_id, status_data):
        """Atualiza o status do processamento"""
        try:
            # Webhook local
            requests.post('http://localhost:5000/api/v1/intelligence/status', json={
                'document_id': document_id,
                **status_data
            })
        except:
            pass # Falha silenciosa do webhook local

def process_document(file_path, title, requires_cadu_format=False):
    """Função auxiliar para processar documento"""
    service = IntelligenceService()
    return service.process_document(file_path, title, requires_cadu_format)

def delete_document(document_id, delete_from='both'):
    """Função auxiliar para deletar documento"""
    service = IntelligenceService()
    
    db = get_db()
    cursor = db.cursor()
    
    # Buscar IDs do Pinecone
    cursor.execute("SELECT pinecone_ids FROM intelligence_documents WHERE id = %s", (document_id,))
    result = cursor.fetchone()
    
    if result and (delete_from in ['pinecone', 'both']):
        pinecone_ids = result[0]
        if pinecone_ids:
            # Deletar do Pinecone
            service.index.delete(ids=pinecone_ids)
    
    if delete_from in ['database', 'both']:
        # Deletar do banco de dados
        cursor.execute("DELETE FROM intelligence_chunks WHERE document_id = %s", (document_id,))
        cursor.execute("DELETE FROM intelligence_documents WHERE id = %s", (document_id,))
        db.commit()
    
    return True

def get_document_stats():
    """Função auxiliar para buscar estatísticas"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_documents,
            SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
            (SELECT COUNT(*) FROM intelligence_chunks) as total_chunks
        FROM intelligence_documents
    """)
    
    result = cursor.fetchone()
    
    return {
        'total_documents': result[0],
        'processing': result[1],
        'total_chunks': result[2]
    }