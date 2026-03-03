"""
Serviço de Geração de Imagens para Audiências via OpenRouter
Utiliza Gemini 2.5 Flash para preparar prompts e GPT-5 Image para gerar imagens
"""

import requests
import os
from typing import Dict, Optional
import logging
from flask import request

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY não encontrada no .env")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_base_url():
    """Detecta automaticamente a URL base baseado na requisição"""
    try:
        # Tenta pegar da requisição atual
        if request:
            scheme = request.scheme  # http ou https
            host = request.host  # localhost:5000 ou dominio.com
            return f"{scheme}://{host}"
    except:
        pass
    
    # Fallback para variável de ambiente ou localhost
    return os.getenv('BASE_URL', 'http://localhost:5000')

# System prompt para o Gemini 2.5 Flash
SYSTEM_PROMPT_PREPARADOR = {
    "role": "Ultra-realistic editorial photography prompt specialist",
    "objective": "Receive audience text and generate one optimized image prompt in English for a 1:1 square photo",
    "style": {
        "mandatory": "Ultra-realistic editorial photography — the image must look like a real photograph taken by a professional photographer",
        "forbidden": [
            "Illustration",
            "3D render",
            "Cartoon",
            "Digital art",
            "Anime",
            "Painting",
            "Watercolor",
            "Sketch"
        ]
    },
    "process": {
        "extract": [
            "Age range",
            "Gender/diversity",
            "Core values",
            "Consumer behavior",
            "Aspirations",
            "Desired emotions",
            "Context/environment",
            "Product or service offered"
        ],
        "choose_visual_approach": "Pick ONE of the two approaches below based on audience context",
        "generate_prompt": [
            "Structured and specific",
            "Ultra-realistic photographic style",
            "Include: lighting + scene + subject + emotion + environment",
            "Optimized for 1:1 square format",
            "80-150 words"
        ]
    },
    "response_format": {
        "optimized_prompt": "Single English prompt ready for AI image generators with 1:1 square specification"
    },
    "visual_approaches": {
        "A_PRODUCT_HERO": {
            "when": "The product, service, or object IS the star of the image",
            "description": "Center the product in a styled real-world setting with context clues that connect it to the audience",
            "example": "A ultra-realistic editorial photograph of a premium organic skincare set arranged on a marble bathroom shelf, soft diffused morning light from a frosted window, eucalyptus sprigs and a white cotton towel beside the bottles, shallow depth of field with creamy bokeh background, clean and luxurious atmosphere, square composition, 1:1 aspect ratio"
        },
        "B_PERSON_LIFESTYLE_HERO": {
            "when": "A person representing the audience IS the star of the image",
            "description": "Show a real-looking person in their natural habitat doing something authentic that reflects their lifestyle, values, or aspirations",
            "example": "A ultra-realistic editorial photograph of a Brazilian woman in her early 30s sitting at a sunlit co-working space, working on a laptop with a warm smile, golden hour light streaming through large windows, modern minimalist decor with plants, natural skin texture and authentic expression, relaxed confident posture, square composition, 1:1 aspect ratio"
        }
    },
    "lighting_guidelines": [
        "Describe lighting by visual effect, not camera specs",
        "Use terms like: golden hour, soft diffused light, warm natural light, overcast soft light, studio rim light, backlit silhouette",
        "Avoid technical camera jargon (f-stop, ISO, shutter speed)"
    ],
    "rules": [
        "Output only the final prompt",
        "No emojis",
        "English only",
        "Always specify 1:1 square composition and aspect ratio",
        "80-150 words",
        "Ready to copy and use immediately",
        "NEVER include text, logos, or watermarks in the image",
        "NEVER depict real celebrities or public figures",
        "Default to Brazilian context (people, settings, culture) unless the audience clearly indicates another country",
        "Ensure ethnic diversity when depicting people — reflect Brazil's multicultural population",
        "Always describe realistic skin texture, natural expressions, and authentic body language",
        "Include specific lighting description using visual-effect terms"
    ]
}


def preparar_prompt_imagem(nome_audiencia: str, categoria: str, descricao: str) -> Dict:
    """
    Chama Gemini 2.5 Flash no OpenRouter para preparar prompt de imagem otimizado
    
    Args:
        nome_audiencia: Nome da audiência
        categoria: Categoria da audiência
        descricao: Descrição detalhada da audiência
    
    Returns:
        Dict com success (bool) e prompt (str) ou error (str)
    """
    try:
        user_message = f"""
Audiência: {nome_audiencia}
Categoria: {categoria}
Descrição: {descricao}

Gere um prompt otimizado em inglês para criar uma imagem representativa desta audiência.
"""
        
        # Tenta primeiro com Gemini gratuito, depois fallback para modelo pago
        models_to_try = [
            "google/gemini-2.0-flash-exp:free",
            "openai/gpt-4o-mini"  # Fallback pago caso rate limit
        ]
        
        last_error = None
        
        for model in models_to_try:
            try:
                response = requests.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://aicentralv2.centralcomm.media",
                        "X-Title": "AI Central v2 - Image Generator"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": str(SYSTEM_PROMPT_PREPARADOR)},
                            {"role": "user", "content": user_message}
                        ],
                        "max_tokens": 500
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    prompt = data['choices'][0]['message']['content'].strip()
                    logger.info(f"Prompt preparado com sucesso usando {model} para audiência: {nome_audiencia}")
                    return {"success": True, "prompt": prompt}
                elif response.status_code == 429:
                    # Rate limit - tenta próximo modelo
                    logger.warning(f"Rate limit em {model}, tentando próximo modelo...")
                    last_error = f"Rate limit temporário. Tentando modelo alternativo..."
                    continue
                else:
                    last_error = f"Erro na API OpenRouter: {response.status_code} - {response.text}"
                    logger.error(last_error)
                    continue
                    
            except requests.exceptions.Timeout:
                last_error = f"Timeout ao usar modelo {model}"
                logger.error(last_error)
                continue
            except Exception as e:
                last_error = f"Erro com modelo {model}: {str(e)}"
                logger.error(last_error)
                continue
        
        # Se chegou aqui, todos os modelos falharam
        return {"success": False, "error": last_error or "Todos os modelos falharam"}
            
    except requests.exceptions.Timeout:
        error_msg = "Timeout ao preparar prompt - API demorou mais de 30s"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Erro ao preparar prompt: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}


def gerar_imagem_audiencia(prompt: str, modelo: str = "google/gemini-2.5-flash-image") -> Dict:
    """
    Gera imagem via OpenRouter usando modelo escolhido
    
    Args:
        prompt: Prompt otimizado em inglês para geração da imagem
        modelo: ID do modelo no OpenRouter (ex: "openai/dall-e-3")
    
    Returns:
        Dict com success (bool) e image_url (str) ou error (str)
    """
    try:
        print(f"\n{'='*80}")
        print(f"Gerando imagem com: {modelo}")
        print(f"Prompt: {prompt[:100]}...")
        print('='*80)
        
        response = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aicentralv2.centralcomm.media",
                "X-Title": "AI Central v2"
            },
            json={
                "model": modelo,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=120
        )
        
        print(f"STATUS: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"RESPONSE KEYS: {list(data.keys())}")
            
            # Extrair URL/base64 da resposta
            image_url = extrair_url_imagem(data)
            
            if image_url:
                print(f"✅ SUCESSO! URL: {image_url}")
                return {"success": True, "image_url": image_url}
            else:
                error_msg = f"Modelo {modelo} não retornou imagem"
                print(f"❌ {error_msg}")
                return {"success": False, "error": error_msg}
        else:
            error_msg = f"Erro {response.status_code}: {response.text[:300]}"
            print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}
        
    except requests.exceptions.Timeout:
        error_msg = "Timeout ao gerar imagem (>90s)"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Erro ao gerar imagem: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}


def extrair_url_imagem(response_data: Dict) -> Optional[str]:
    """
    Extrai URL da imagem da resposta do OpenRouter
    Para Gemini Image, decodifica base64 e salva localmente
    """
    import base64
    import random
    from datetime import datetime
    from pathlib import Path
    
    print("=" * 80)
    print("EXTRAIR_URL_IMAGEM CHAMADA!")
    print("=" * 80)
    
    try:
        print(f"Response keys: {list(response_data.keys())}")
        
        # Gemini 2.5 Flash Image: base64 em choices[0]['message']['content'][0]['data']
        if 'choices' not in response_data:
            print("ERRO: 'choices' nao encontrado na resposta")
            return None
            
        if len(response_data['choices']) == 0:
            print("ERRO: lista 'choices' vazia")
            return None
        
        choice = response_data['choices'][0]
        print(f"Choice keys: {list(choice.keys())}")
        
        if 'message' not in choice:
            print("ERRO: 'message' nao encontrado em choice")
            return None
        
        message = choice['message']
        print(f"Message keys: {list(message.keys())}")
        print(f"Content type: {type(message.get('content'))}")
        
        # GEMINI 2.5 FLASH IMAGE: imagens vem em message['images']!
        if 'images' in message and isinstance(message['images'], list):
            print(f"IMAGES encontrado! Total: {len(message['images'])} imagens")
            
            for i, img in enumerate(message['images']):
                print(f"Imagem {i}: type={type(img)}")
                if isinstance(img, dict):
                    print(f"  Keys: {list(img.keys())}")
                    
                    # Verificar se tem 'image_url' (formato OpenRouter)
                    if 'image_url' in img:
                        if isinstance(img['image_url'], dict) and 'url' in img['image_url']:
                            url = img['image_url']['url']
                            print(f"✅ URL encontrada em image_url.url: {url[:100]}")
                            
                            # Se for base64, salvar localmente
                            if url.startswith('data:image'):
                                print("Base64 detectado, extraindo...")
                                base64_data = url.split(',')[1]
                                image_bytes = base64.b64decode(base64_data)
                                print(f"DECODIFICADO! {len(image_bytes)} bytes")
                                
                                upload_dir = Path("aicentralv2/static/uploads/audiencias")
                                upload_dir.mkdir(parents=True, exist_ok=True)
                                
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                random_id = random.randint(1000, 9999)
                                filename = f"gemini_{timestamp}_{random_id}.png"
                                filepath = upload_dir / filename
                                
                                with open(filepath, 'wb') as f:
                                    f.write(image_bytes)
                                
                                # URL completa para acesso externo
                                base_url = get_base_url()
                                public_url = f"{base_url}/static/uploads/audiencias/{filename}"
                                print(f"SUCESSO! Imagem salva: {public_url}")
                                print("=" * 80)
                                return public_url
                            else:
                                # URL direta
                                print(f"URL direta retornada!")
                                print("=" * 80)
                                return url
                        elif isinstance(img['image_url'], str):
                            url = img['image_url']
                            print(f"✅ URL string encontrada: {url[:100]}")
                            print("=" * 80)
                            return url
                    
                    # Pode vir como 'data' ou 'image_data' ou 'base64' (formato antigo)
                    for key in ['data', 'image_data', 'base64', 'content']:
                        if key in img:
                            base64_data = img[key]
                            print(f"BASE64 ENCONTRADO em '{key}'! Tamanho: {len(base64_data)} chars")
                            print(f"Primeiros 50 chars: {base64_data[:50]}")
                            
                            # Decodificar base64
                            image_bytes = base64.b64decode(base64_data)
                            print(f"DECODIFICADO! {len(image_bytes)} bytes")
                            
                            # Criar diretório
                            upload_dir = Path("aicentralv2/static/uploads/audiencias")
                            upload_dir.mkdir(parents=True, exist_ok=True)
                            print(f"Diretorio criado: {upload_dir}")
                            
                            # Salvar arquivo
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            random_id = random.randint(1000, 9999)
                            filename = f"gemini_{timestamp}_{random_id}.png"
                            filepath = upload_dir / filename
                            
                            with open(filepath, 'wb') as f:
                                f.write(image_bytes)
                            
                            # URL completa para acesso externo
                            base_url = get_base_url()
                            public_url = f"{base_url}/static/uploads/audiencias/{filename}"
                            print(f"SUCESSO! Imagem salva: {public_url}")
                            print("=" * 80)
                            return public_url
        
        print("ERRO: Nenhuma imagem encontrada em message['images']")
        print("=" * 80)
        return None
        
    except Exception as e:
        print("=" * 80)
        print(f"EXCEPTION CAPTURADA: {e}")
        print(f"Tipo: {type(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return None


def armazenar_imagem_local(temp_url: str, audiencia_id: int) -> Optional[str]:
    """
    Download da imagem do OpenRouter e salva localmente
    
    Args:
        temp_url: URL temporária da imagem gerada
        audiencia_id: ID da audiência
    
    Returns:
        URL pública da imagem ou None em caso de erro
    """
    try:
        from datetime import datetime
        from pathlib import Path
        
        # Download da imagem
        response = requests.get(temp_url, stream=True, timeout=30)
        if response.status_code != 200:
            logger.error(f"Erro ao baixar imagem: HTTP {response.status_code}")
            return None
        
        # Criar diretório se não existir
        upload_dir = Path("aicentralv2/static/uploads/audiencias")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Salvar arquivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"audiencia_{audiencia_id}_{timestamp}.png"
        filepath = upload_dir / filename
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # URL pública relativa
        public_url = f"/static/uploads/audiencias/{filename}"
        logger.info(f"Imagem armazenada localmente: {public_url}")
        return public_url
        
    except Exception as e:
        logger.error(f"Erro ao armazenar imagem: {e}")
        return None
