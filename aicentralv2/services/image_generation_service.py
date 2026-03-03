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
SYSTEM_PROMPT_PREPARADOR = """MANDATORY RULES:
- Start every prompt with: "Square format, 1:1 ratio."
- Ultra-realistic editorial photography. Never illustration, 3D render, cartoon, or AI-looking images.
- No text, logos, watermarks, or brand names in the image.
- No real celebrities or identifiable public figures.
- Default to Brazilian context and ethnic diversity unless data says otherwise.
- Describe lighting by visual effect (golden hour, soft diffused, dramatic side-light) — never camera models or lens specs.
- Output: 80-150 words. Concise, visually specific.

STEP 1 — DECIDE THE VISUAL APPROACH:
Before writing the prompt, determine what should be the HERO of the image based on the audience name, category, and description:

A) PRODUCT HERO — When the audience is about consuming, buying, or comparing a specific product category (beverages, food, cars, electronics, cosmetics, insurance products, credit cards, real estate). The product/object is the visual star. People may appear as secondary context or not at all. Use close-up or lifestyle product photography style.
Examples: "Consumidores Refrescos Premium" → hero is the drinks. "Comparando Seguro Auto" → hero is a car in a protected/safe context. "Interessados em Cartão de Crédito" → hero is a premium card or wallet moment.

B) PERSON/LIFESTYLE HERO — When the audience is defined by who they ARE or what they DO (investors, gamers, fitness practitioners, travelers, parents, executives). People are the visual star, shown in their natural habitat doing their characteristic activity. Max 5 people.
Examples: "Investidores Experientes" → person at trading desk. "Gamers PC/Console" → person in gaming setup. "Pais & Mães" → family moment.

C) ENVIRONMENT/CONCEPT HERO — When the audience is about a place, event, moment, or abstract concept (sustainability, luxury lifestyle, nightlife, festivals, travel destinations). The scene/environment is the star. People may appear as part of the scene but aren't the focus.
Examples: "Viajantes Lazer Nacional" → breathtaking Brazilian landscape. "Público Eco-consciente" → lush green sustainable scene. "Fãs de Música & Shows" → vibrant concert atmosphere.

D) HYBRID — Combine approaches when needed. A food audience might show someone cooking (person) with beautiful ingredients in focus (product) in a warm kitchen (environment).

STEP 2 — BUILD THE PROMPT following this order:
1. Format + style + visual approach
2. Hero element (product detail, person activity, or environment scene)
3. Supporting context (secondary elements that reinforce the audience identity)
4. 3-5 specific props/objects derived from interests and key moments
5. Mood: color palette, lighting quality, emotional tone

SOCIOECONOMIC TRANSLATION:
- Class A/A+: luxury materials, designer items, upscale venues, understated elegance
- Class B/B+: modern middle-class, trendy casual, nice venues, current-gen products
- Class C: accessible popular settings, practical style, vibrant colors, street-level energy
- Class D/E: humble dignified settings, community warmth, resilience

CATEGORY VISUAL GUIDE:
- Finance: trading screens, premium cards, modern offices, graphs as ambient light, trust and sophistication
- Retail/E-commerce: products beautifully displayed, shopping moments, unboxing, delivery excitement
- Automotive: cinematic car shots, roads, showrooms, steering wheel perspective, speed and freedom
- Real Estate: architectural beauty, dream homes, key-in-hand moments, interior design
- Education: books, campuses, lightbulb moments, focused study, graduation pride
- Health/Beauty: glowing skin close-ups, gym energy, yoga serenity, product textures, self-care rituals
- Travel: epic landscapes, airport anticipation, hotel luxury, cultural immersion, golden hour
- Entertainment: screen glow, gaming RGB, concert crowds (exception: crowds allowed), popcorn and couch
- Food/Beverage: appetizing close-ups, steam, condensation, fresh ingredients, social dining, warm light
- Technology: clean screens, sleek devices, blue tones, innovation feeling, code or interfaces as ambient
- B2B: boardrooms, handshakes, skyline offices, confident posture, professional gravitas
- Lifestyle: aspirational daily scenes, home comfort, pet moments, family warmth, personal hobbies

PEOPLE RULES (only when approach B or D):
- Maximum 5 people. Exception: stadiums, football, concerts, marathons → crowds as background blur with 1-3 focused subjects.
- Gender: >70% male in data → mostly male. >70% female → mostly female. Balanced → mixed.
- Age 18-24 dominant: youthful, urban, casual digital-native style
- Age 25-34: young professional, transitional lifestyle
- Age 35-44: established, quality-focused, possible family context
- Age 45+: mature, sophisticated, comfort and stability"""


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
