from flask import Blueprint, render_template, request, jsonify, abort
from aicentralv2.auth import login_required
import os
from ..services.intelligence.service import process_document, delete_document, get_document_stats
from ..db import get_db

bp = Blueprint('intelligence', __name__, url_prefix='/intelligence')

@bp.route('/')
@login_required
def index():
    db = get_db()
    cursor = db.cursor()
    
    # Buscar estatísticas
    stats = get_document_stats()
    
    # Buscar documentos
    cursor.execute("""
        SELECT 
            id, title, status, created_at, metadata, 
            (SELECT COUNT(*) FROM intelligence_chunks WHERE document_id = d.id) as chunks_count
        FROM intelligence_documents d
        ORDER BY created_at DESC
        LIMIT 10
    """)
    documents = cursor.fetchall()
    
    return render_template('intelligence/index.html', 
                         documents=documents,
                         stats=stats)

@bp.route('/view/<int:document_id>')
@login_required
def view(document_id):
    db = get_db()
    cursor = db.cursor()
    
    # Buscar documento
    cursor.execute("""
        SELECT 
            d.*,
            (SELECT COUNT(*) FROM intelligence_chunks WHERE document_id = d.id) as chunks_count
        FROM intelligence_documents d
        WHERE d.id = %s
    """, (document_id,))
    
    document = cursor.fetchone()
    if not document:
        abort(404)
        
    return render_template('intelligence/view.html', document=document)

@bp.route('/api/v1/intelligence/process', methods=['POST'])
@login_required
def process():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'})
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado'})
        
    if file:
        # Salvar arquivo temporariamente
        temp_path = os.path.join('/tmp', file.filename)
        file.save(temp_path)
        
        try:
            # Iniciar processamento
            document = process_document(
                file_path=temp_path,
                title=request.form.get('title'),
                requires_cadu_format=request.form.get('requires_cadu_format') == 'on'
            )
            
            return jsonify({
                'success': True,
                'document_id': document['id']
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            })
        finally:
            # Limpar arquivo temporário
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    return jsonify({'success': False, 'message': 'Erro ao processar arquivo'})

@bp.route('/api/v1/intelligence/delete', methods=['POST'])
@login_required
def delete():
    data = request.get_json()
    document_id = data.get('document_id')
    delete_from = data.get('delete_from', 'both')
    
    try:
        delete_document(document_id, delete_from)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@bp.route('/api/v1/intelligence/status', methods=['POST'])
def update_status():
    """Webhook para atualização de status do processamento"""
    data = request.get_json()
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            UPDATE intelligence_documents
            SET status = %s,
                pinecone_ids = %s,
                metadata = jsonb_set(
                    metadata,
                    '{processing_stats}',
                    %s::jsonb
                )
            WHERE id = %s
        """, (
            data['status'],
            data['pinecone_ids'],
            {
                'chunks_processed': data['chunks_processed'],
                'total_chunks': data['total_chunks'],
                'error_message': data.get('error_message')
            },
            data['document_id']
        ))
        
        db.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        })
