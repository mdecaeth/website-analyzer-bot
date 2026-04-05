"""
Website Analyzer Bot - Web App
Analizza siti web e genera prompt ottimizzati per Lovable
"""

from flask import Flask, render_template_string, request, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import re
import webbrowser
import threading

app = Flask(__name__)

def extract_business_info(soup, url):
    """Estrae informazioni dettagliate sul business/azienda."""
    info = {
        'name': '',
        'description': '',
        'services': [],
        'industry': '',
        'tagline': ''
    }

    # Nome azienda dal titolo
    title = soup.find('title')
    if title:
        title_text = title.get_text(strip=True)
        # Prendi la prima parte prima di | - o :
        info['name'] = re.split(r'[|\-:]', title_text)[0].strip()

    # Meta description
    meta_desc = soup.find('meta', {'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        info['description'] = meta_desc.get('content', '').strip()

    # OG description come fallback
    if not info['description']:
        og_desc = soup.find('meta', {'property': 'og:description'})
        if og_desc and og_desc.get('content'):
            info['description'] = og_desc.get('content', '').strip()

    # Tagline da h1 o primo heading importante
    h1 = soup.find('h1')
    if h1:
        info['tagline'] = h1.get_text(strip=True)[:150]

    # Estrai servizi/prodotti dai menu e headings
    services = set()
    for nav in soup.find_all(['nav', 'header']):
        for link in nav.find_all('a'):
            text = link.get_text(strip=True)
            if text and 3 < len(text) < 30 and not text.lower() in ['home', 'contact', 'about', 'blog', 'login', 'contatto', 'chi siamo']:
                services.add(text)

    # Aggiungi h2 come potenziali servizi/sezioni
    for h2 in soup.find_all('h2')[:6]:
        text = h2.get_text(strip=True)
        if text and 3 < len(text) < 50:
            services.add(text)

    info['services'] = list(services)[:8]

    # Determina l'industria basandosi su keywords
    html_lower = str(soup).lower()
    industries = {
        'veterinario': ['veterinar', 'pet', 'animal', 'clinic', 'vet ', 'cane', 'gatto', 'animali'],
        'ristorante': ['restaurant', 'menu', 'food', 'cuisine', 'ristorante', 'cucina', 'chef'],
        'e-commerce': ['shop', 'cart', 'buy', 'product', 'store', 'acquista', 'carrello'],
        'studio legale': ['law', 'legal', 'attorney', 'avvocato', 'legale', 'studio legale'],
        'agenzia marketing': ['marketing', 'agency', 'digital', 'seo', 'social media', 'agenzia'],
        'studio medico': ['doctor', 'medical', 'health', 'clinic', 'medico', 'salute', 'pazient'],
        'immobiliare': ['real estate', 'property', 'immobil', 'casa', 'appartament', 'affitto'],
        'fitness/palestra': ['gym', 'fitness', 'workout', 'training', 'palestra', 'allenamento'],
        'hotel/hospitality': ['hotel', 'booking', 'room', 'hospitality', 'prenotazion', 'camera'],
        'educazione': ['school', 'education', 'course', 'learn', 'scuola', 'corso', 'formazione'],
        'tecnologia/software': ['software', 'tech', 'app', 'platform', 'saas', 'solution'],
        'consulenza': ['consult', 'advisory', 'business', 'consulen', 'servizi'],
        'architettura/design': ['architect', 'design', 'interior', 'architettura', 'progett'],
        'fotografo': ['photo', 'photography', 'photographer', 'foto', 'shooting'],
        'salone bellezza': ['salon', 'beauty', 'hair', 'spa', 'wellness', 'bellezza', 'parrucchier'],
    }

    for industry, keywords in industries.items():
        if any(kw in html_lower for kw in keywords):
            info['industry'] = industry
            break

    if not info['industry']:
        info['industry'] = 'servizi professionali'

    return info

def find_logo(soup, base_url):
    """Trova il logo del sito e restituisce URL e info."""
    logo_info = {
        'url': None,
        'found': False
    }

    # Cerca immagini con "logo" nel nome, class, id o alt
    logo_patterns = ['logo', 'brand', 'site-logo', 'header-logo']

    for img in soup.find_all('img'):
        src = img.get('src', '')
        alt = img.get('alt', '').lower()
        img_class = ' '.join(img.get('class', [])).lower() if img.get('class') else ''
        img_id = (img.get('id') or '').lower()

        if any(p in src.lower() or p in alt or p in img_class or p in img_id for p in logo_patterns):
            logo_info['url'] = urljoin(base_url, src)
            logo_info['found'] = True
            break

    # Fallback: cerca nel header la prima immagine
    if not logo_info['found']:
        header = soup.find('header') or soup.find('nav')
        if header:
            first_img = header.find('img')
            if first_img and first_img.get('src'):
                logo_info['url'] = urljoin(base_url, first_img['src'])
                logo_info['found'] = True

    # Fallback: favicon/apple-touch-icon
    if not logo_info['found']:
        for link in soup.find_all('link', rel=True):
            rel = ' '.join(link.get('rel', []))
            if 'icon' in rel or 'apple-touch' in rel:
                href = link.get('href')
                if href:
                    logo_info['url'] = urljoin(base_url, href)
                    logo_info['found'] = True
                    break

    return logo_info

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Website Analyzer Bot</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #fff;
        }

        .container {
            max-width: 1000px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        header {
            text-align: center;
            margin-bottom: 40px;
        }

        h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #e94560, #ff6b6b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .subtitle {
            color: #a0a0a0;
            font-size: 1.1rem;
        }

        .input-section {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }

        .input-group {
            display: flex;
            gap: 15px;
        }

        input[type="text"] {
            flex: 1;
            padding: 16px 20px;
            border: 2px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-size: 1rem;
            transition: all 0.3s ease;
        }

        input[type="text"]:focus {
            outline: none;
            border-color: #e94560;
            box-shadow: 0 0 20px rgba(233,69,96,0.3);
        }

        input[type="text"]::placeholder {
            color: #666;
        }

        button {
            padding: 16px 32px;
            background: linear-gradient(90deg, #e94560, #ff6b6b);
            border: none;
            border-radius: 12px;
            color: #fff;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(233,69,96,0.4);
        }

        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .loading {
            display: none;
            text-align: center;
            padding: 40px;
        }

        .loading.active {
            display: block;
        }

        .spinner {
            width: 50px;
            height: 50px;
            border: 4px solid rgba(255,255,255,0.1);
            border-top-color: #e94560;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .results {
            display: none;
        }

        .results.active {
            display: block;
        }

        .report-card {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }

        .report-card h3 {
            color: #e94560;
            margin-bottom: 15px;
            font-size: 1.2rem;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }

        .stat-item {
            background: rgba(0,0,0,0.2);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }

        .stat-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: #ff6b6b;
        }

        .stat-label {
            font-size: 0.85rem;
            color: #888;
            margin-top: 5px;
        }

        .tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .tag {
            background: rgba(233,69,96,0.2);
            color: #ff6b6b;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
        }

        .prompt-section {
            background: rgba(0,0,0,0.3);
            border-radius: 16px;
            padding: 25px;
            margin-top: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }

        .prompt-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .prompt-header h3 {
            color: #e94560;
        }

        .copy-btn {
            padding: 10px 20px;
            font-size: 0.9rem;
        }

        .prompt-text {
            background: rgba(0,0,0,0.4);
            padding: 20px;
            border-radius: 10px;
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 0.9rem;
            line-height: 1.6;
            white-space: pre-wrap;
            max-height: 500px;
            overflow-y: auto;
            color: #ddd;
        }

        .copied-toast {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #2ecc71;
            color: #fff;
            padding: 15px 25px;
            border-radius: 10px;
            font-weight: 600;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s ease;
        }

        .copied-toast.show {
            transform: translateY(0);
            opacity: 1;
        }

        .error {
            background: rgba(231,76,60,0.2);
            border: 1px solid #e74c3c;
            color: #ff6b6b;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            display: none;
        }

        .error.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Website Analyzer Bot</h1>
            <p class="subtitle">Analizza siti web e genera prompt perfetti per Lovable</p>
        </header>

        <div class="input-section">
            <div class="input-group">
                <input type="text" id="urlInput" placeholder="Inserisci l'URL del sito (es. stripe.com)">
                <button id="analyzeBtn" onclick="analyzeWebsite()">Analizza</button>
            </div>
        </div>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Analisi in corso...</p>
        </div>

        <div class="error" id="error"></div>

        <div class="results" id="results">
            <div class="report-card">
                <h3>Informazioni Business</h3>
                <div id="businessInfo" style="line-height: 1.8;"></div>
            </div>

            <div class="report-card" id="logoCard" style="display: none;">
                <h3>Logo Trovato</h3>
                <div style="display: flex; align-items: center; gap: 20px;">
                    <img id="logoImg" src="" alt="Logo" style="max-height: 80px; max-width: 200px; background: #fff; padding: 10px; border-radius: 8px;">
                    <p style="color: #888; font-size: 0.9rem;">I colori del logo verranno usati come base per la palette del sito</p>
                </div>
            </div>

            <div class="report-card">
                <h3>Struttura Rilevata</h3>
                <div class="stats-grid" id="stats"></div>
            </div>

            <div class="report-card">
                <h3>Funzionalita Rilevate</h3>
                <div class="tags" id="features"></div>
            </div>

            <div class="prompt-section">
                <div class="prompt-header">
                    <h3>Prompt per Lovable</h3>
                    <button class="copy-btn" onclick="copyPrompt()">Copia Prompt</button>
                </div>
                <div class="prompt-text" id="prompt"></div>
            </div>
        </div>
    </div>

    <div class="copied-toast" id="toast">Prompt copiato!</div>

    <script>
        async function analyzeWebsite() {
            const url = document.getElementById('urlInput').value.trim();
            if (!url) {
                showError('Inserisci un URL valido');
                return;
            }

            document.getElementById('loading').classList.add('active');
            document.getElementById('results').classList.remove('active');
            document.getElementById('error').classList.remove('active');
            document.getElementById('analyzeBtn').disabled = true;

            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });

                const data = await response.json();

                if (data.error) {
                    showError(data.error);
                } else {
                    displayResults(data);
                }
            } catch (err) {
                showError('Errore di connessione');
            }

            document.getElementById('loading').classList.remove('active');
            document.getElementById('analyzeBtn').disabled = false;
        }

        function showError(message) {
            const error = document.getElementById('error');
            error.textContent = message;
            error.classList.add('active');
        }

        function displayResults(data) {
            // Business Info
            const businessInfo = document.getElementById('businessInfo');
            let businessHtml = '';
            if (data.business) {
                if (data.business.name) businessHtml += `<div><strong>Azienda:</strong> ${data.business.name}</div>`;
                if (data.business.industry) businessHtml += `<div><strong>Settore:</strong> ${data.business.industry}</div>`;
                if (data.business.description) businessHtml += `<div><strong>Descrizione:</strong> ${data.business.description}</div>`;
                if (data.business.services && data.business.services.length > 0) {
                    businessHtml += `<div><strong>Servizi/Sezioni:</strong> ${data.business.services.join(', ')}</div>`;
                }
            }
            businessInfo.innerHTML = businessHtml || '<div style="color:#888">Informazioni non disponibili</div>';

            // Logo
            const logoCard = document.getElementById('logoCard');
            const logoImg = document.getElementById('logoImg');
            if (data.logo && data.logo.found && data.logo.url) {
                logoImg.src = data.logo.url;
                logoCard.style.display = 'block';
            } else {
                logoCard.style.display = 'none';
            }

            // Stats
            const stats = document.getElementById('stats');
            stats.innerHTML = `
                <div class="stat-item">
                    <div class="stat-value">${data.structure.sections}</div>
                    <div class="stat-label">Sezioni</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${data.structure.images}</div>
                    <div class="stat-label">Immagini</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${data.structure.buttons}</div>
                    <div class="stat-label">Pulsanti</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${data.structure.forms}</div>
                    <div class="stat-label">Form</div>
                </div>
            `;

            // Features
            const features = document.getElementById('features');
            const allFeatures = [...data.features];
            if (data.purpose) allFeatures.unshift(data.purpose);
            if (data.layout.framework) allFeatures.push(data.layout.framework);
            if (data.animations.has_animations) allFeatures.push('Animazioni');
            features.innerHTML = allFeatures.map(f => `<span class="tag">${f}</span>`).join('');

            // Prompt
            document.getElementById('prompt').textContent = data.prompt;

            document.getElementById('results').classList.add('active');
        }

        function copyPrompt() {
            const prompt = document.getElementById('prompt').textContent;
            navigator.clipboard.writeText(prompt).then(() => {
                const toast = document.getElementById('toast');
                toast.classList.add('show');
                setTimeout(() => toast.classList.remove('show'), 2000);
            });
        }

        document.getElementById('urlInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') analyzeWebsite();
        });
    </script>
</body>
</html>
"""

def fetch_website(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.text
    except:
        return None

def extract_colors(html, soup):
    colors = set()
    hex_pattern = r'#[0-9a-fA-F]{3,6}\b'
    colors.update(re.findall(hex_pattern, html))
    rgb_pattern = r'rgba?\([^)]+\)'
    colors.update(re.findall(rgb_pattern, html))
    return list(colors)[:10]

def extract_fonts(html, soup):
    fonts = set()
    font_pattern = r'font-family:\s*([^;}"\']+)'
    matches = re.findall(font_pattern, html, re.IGNORECASE)
    for match in matches:
        fonts.add(match.strip().strip('"\''))
    return list(fonts)[:5]

def analyze_structure(soup):
    return {
        'has_header': bool(soup.find('header') or soup.find('nav')),
        'has_footer': bool(soup.find('footer')),
        'has_hero': bool(soup.find(class_=re.compile(r'hero|banner|jumbotron', re.I))),
        'sections': len(soup.find_all('section')),
        'has_sidebar': bool(soup.find('aside')),
        'forms': len(soup.find_all('form')),
        'buttons': len(soup.find_all('button')) + len(soup.find_all('a', class_=re.compile(r'btn|button', re.I))),
        'images': len(soup.find_all('img')),
    }

def detect_animations(html):
    animations = {
        'has_transitions': 'transition' in html.lower(),
        'has_animations': 'animation' in html.lower(),
        'animation_libraries': []
    }
    libs = {'aos': 'AOS', 'gsap': 'GSAP', 'framer-motion': 'Framer Motion'}
    for lib, name in libs.items():
        if lib in html.lower():
            animations['animation_libraries'].append(name)
    return animations

def detect_features(html, soup):
    features = []
    checks = [
        ('search', 'Ricerca'),
        ('carousel', 'Carousel'), ('slider', 'Slider'),
        ('modal', 'Modal'), ('accordion', 'Accordion'),
        ('testimonial', 'Testimonials'), ('pricing', 'Pricing'),
        ('faq', 'FAQ'), ('newsletter', 'Newsletter'),
    ]
    for keyword, name in checks:
        if keyword in html.lower():
            features.append(name)
    return list(set(features))

def analyze_layout(soup):
    html = str(soup)
    layout = {'type': 'Standard', 'responsive': 'media' in html.lower()}
    if 'bootstrap' in html.lower():
        layout['framework'] = 'Bootstrap'
    elif 'tailwind' in html.lower():
        layout['framework'] = 'Tailwind CSS'
    return layout

def get_purpose(soup):
    html = str(soup).lower()
    if any(w in html for w in ['shop', 'cart', 'product', 'ecommerce']):
        return 'E-commerce'
    elif any(w in html for w in ['portfolio', 'projects']):
        return 'Portfolio'
    elif any(w in html for w in ['blog', 'article']):
        return 'Blog'
    elif any(w in html for w in ['saas', 'software', 'platform']):
        return 'SaaS'
    elif any(w in html for w in ['agency', 'company', 'services']):
        return 'Corporate'
    return 'Website'

def extract_navigation(soup):
    nav_items = []
    nav = soup.find('nav') or soup.find('header')
    if nav:
        for link in nav.find_all('a')[:8]:
            text = link.get_text(strip=True)
            if text and len(text) < 25:
                nav_items.append(text)
    return nav_items

def generate_business_narrative(business, url):
    """Genera una descrizione narrativa e coesa del business."""
    name = business.get('name', 'L\'azienda')
    industry = business.get('industry', 'servizi professionali')
    description = business.get('description', '')
    tagline = business.get('tagline', '')
    services = business.get('services', [])

    # Costruisci il paragrafo narrativo
    narrative = f"{name} e un'azienda che opera nel settore {industry}. "

    if description:
        narrative += f"{description} "

    if tagline and tagline != name:
        narrative += f"Il loro motto/messaggio principale e: \"{tagline}\". "

    if services:
        services_clean = [s for s in services if len(s) > 2 and s.lower() not in ['home', 'menu', 'contact']][:5]
        if services_clean:
            narrative += f"L'azienda offre i seguenti servizi/sezioni: {', '.join(services_clean)}. "

    # Aggiungi contesto sul tipo di comunicazione
    industry_context = {
        'veterinario': "Il sito deve trasmettere cura, professionalita medica e amore per gli animali. Il tono deve essere rassicurante per i proprietari di animali domestici, mostrando competenza veterinaria e empatia.",
        'ristorante': "Il sito deve stimolare l'appetito e trasmettere l'atmosfera del locale. Deve mostrare il menu in modo appetitoso e facilitare le prenotazioni.",
        'e-commerce': "Il sito deve facilitare gli acquisti, mostrare i prodotti in modo attraente e costruire fiducia per le transazioni online.",
        'studio legale': "Il sito deve comunicare autorevevolezza, competenza legale e riservatezza. Il tono deve essere professionale e ispirare fiducia.",
        'agenzia marketing': "Il sito deve essere creativo, moderno e dimostrare le competenze dell'agenzia attraverso il design stesso.",
        'studio medico': "Il sito deve trasmettere professionalita medica, igiene e cura del paziente. Deve essere facile prenotare appuntamenti.",
        'immobiliare': "Il sito deve mostrare le proprieta in modo attraente e facilitare la ricerca di immobili. Deve ispirare fiducia nelle transazioni.",
        'fitness/palestra': "Il sito deve motivare e ispirare, mostrando energia e risultati. Deve facilitare l'iscrizione e mostrare i servizi offerti.",
        'hotel/hospitality': "Il sito deve far sognare il soggiorno, mostrare le camere e i servizi, e rendere facile la prenotazione.",
        'educazione': "Il sito deve trasmettere competenza educativa e facilitare l'iscrizione ai corsi.",
        'tecnologia/software': "Il sito deve essere moderno, mostrare le funzionalita del prodotto e facilitare la conversione.",
        'consulenza': "Il sito deve trasmettere esperienza e competenza, mostrando risultati e casi di successo.",
        'architettura/design': "Il sito deve essere visivamente impressionante, mostrando il portfolio di progetti in modo elegante.",
        'fotografo': "Il sito deve mettere in risalto le foto come protagoniste, con un design minimale che non distragga.",
        'salone bellezza': "Il sito deve trasmettere eleganza, cura e benessere. Deve mostrare i trattamenti e facilitare le prenotazioni.",
    }

    if industry in industry_context:
        narrative += industry_context[industry]
    else:
        narrative += "Il sito deve comunicare professionalita, affidabilita e competenza nel proprio settore."

    return narrative

def generate_prompt(url, analysis):
    business = analysis.get('business', {})
    logo = analysis.get('logo', {})

    # Genera la descrizione narrativa del business
    business_narrative = generate_business_narrative(business, url)

    prompt = f"""Crea un sito web moderno e professionale per la seguente azienda. Il design deve essere significativamente migliore rispetto al sito originale ({url}) in termini di UI/UX, estetica e funzionalita.

## CHI E IL CLIENTE - DESCRIZIONE DEL BUSINESS

{business_narrative}

"""

    # Sezione logo - SEMPRE inclusa se trovato
    if logo.get('found') and logo.get('url'):
        prompt += f"""## LOGO E IDENTITA VISIVA

URL del logo aziendale: {logo['url']}

ISTRUZIONI IMPORTANTI SUL LOGO:
1. Analizza i colori presenti nel logo a questo URL
2. Usa i colori del logo come BASE per tutta la palette del sito:
   - Il colore PRIMARIO del sito deve essere il colore dominante del logo
   - Il colore SECONDARIO deve essere un colore di accento presente nel logo (o un complementare armonioso)
   - I colori neutri (grigi, bianchi, neri) devono bilanciare la palette
3. Mantieni coerenza visiva tra il logo e tutto il design del sito
4. Il logo deve essere posizionato nell'header in modo prominente

"""
    else:
        prompt += """## IDENTITA VISIVA

Non e stato possibile estrarre il logo automaticamente. Usa una palette colori professionale e moderna adatta al settore dell'azienda.

"""

    prompt += f"""## TIPO DI SITO
{analysis['purpose']}

"""

    prompt += "## STRUTTURA RICHIESTA\n"
    s = analysis['structure']
    if s['has_header']:
        prompt += "- Header con logo a sinistra e navigazione pulita\n"
    if s['has_hero']:
        prompt += "- Hero section d'impatto con CTA chiara\n"
    prompt += f"- {max(s['sections'], 3)} sezioni di contenuto ben organizzate\n"
    if s['forms'] > 0:
        prompt += f"- {s['forms']} form con validazione e UX ottimizzata\n"
    if s['has_footer']:
        prompt += "- Footer completo con contatti e link utili\n"

    if analysis['nav_items']:
        prompt += f"\n## NAVIGAZIONE\nVoci menu suggerite: {', '.join(analysis['nav_items'][:6])}\n"

    if analysis['features']:
        prompt += "\n## FUNZIONALITA DA INCLUDERE\n"
        for f in analysis['features']:
            prompt += f"- {f}\n"

    prompt += """
## DESIGN E STILE
- IMPORTANTE: La palette colori DEVE essere basata sui colori estratti dal logo (vedi sezione LOGO E IDENTITA VISIVA sopra)
- Typography: font sans-serif professionale, gerarchia chiara (titoli bold, body leggibile)
- Spaziatura generosa (whitespace) per un look premium
- Border radius morbidi (8-12px) per un aspetto moderno
- Shadows sottili per profondita e elevazione
- Layout responsive (mobile-first)
- Immagini di alta qualita con overlay per leggibilita del testo

## ANIMAZIONI E MICRO-INTERAZIONI
- Transizioni fluide (300ms ease-out) su hover e focus
- Animazioni di entrata al scroll (fade-in-up, stagger per liste)
- Micro-interazioni sui pulsanti (scale 1.02-1.05, shadow elevation)
- Smooth scroll tra le sezioni
- Loading states con skeleton screens

## UX E ACCESSIBILITA
- Feedback visivo immediato su ogni interazione
- Form con validazione inline e messaggi di errore chiari
- CTA evidenti e ben posizionate
- Contrasto accessibile (WCAG AA minimo)
- Focus states visibili per navigazione da tastiera
- Mobile-friendly con touch targets adeguati (min 44px)

## TECH STACK CONSIGLIATO
- React + TypeScript
- Tailwind CSS per lo styling
- Framer Motion per animazioni
- Componenti riutilizzabili e ben organizzati

## NOTE FINALI
1. NON copiare il design originale, ma usalo come ISPIRAZIONE per creare qualcosa di MIGLIORE
2. RICORDA: i colori del sito devono derivare dal logo aziendale per mantenere coerenza di brand
3. Migliora significativamente rispetto all'originale:
   - UI piu pulita, moderna e minimale
   - Migliore gerarchia visiva e leggibilita
   - Animazioni piu fluide e professionali
   - UX piu intuitiva e user-friendly
"""
    return prompt

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    url = data.get('url', '')

    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    html = fetch_website(url)
    if not html:
        return jsonify({'error': 'Impossibile caricare il sito'})

    soup = BeautifulSoup(html, 'html.parser')

    # Estrai informazioni sul business
    business_info = extract_business_info(soup, url)

    # Trova il logo
    logo_info = find_logo(soup, url)

    analysis = {
        'url': url,
        'purpose': get_purpose(soup),
        'structure': analyze_structure(soup),
        'colors': extract_colors(html, soup),
        'fonts': extract_fonts(html, soup),
        'animations': detect_animations(html),
        'layout': analyze_layout(soup),
        'features': detect_features(html, soup),
        'nav_items': extract_navigation(soup),
        'business': business_info,
        'logo': logo_info
    }

    analysis['prompt'] = generate_prompt(url, analysis)

    return jsonify(analysis)

import os

def open_browser():
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    # Se siamo su Render o altro hosting, usa la porta dall'environment
    port = int(os.environ.get('PORT', 5000))

    # Se siamo in locale, apri il browser
    if port == 5000:
        print("\n" + "="*50)
        print("  WEBSITE ANALYZER BOT")
        print("  Apri http://localhost:5000 nel browser")
        print("  Premi CTRL+C per chiudere")
        print("="*50 + "\n")
        threading.Timer(1.5, open_browser).start()

    app.run(host='0.0.0.0', debug=False, port=port)
