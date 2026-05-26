import concurrent.futures
import io
import os
import re
import time
import urllib.parse
import zipfile

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request, send_file
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)


def extract_resources(html_content):
    """
    Analyse le code source HTML d'un Digipad pour en extraire les ressources.
    Récupère les titres, les colonnes, les liens de téléchargement directs 
    et cherche les liens cachés dans le code JSON interne.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    resources_dict = {}
    
    # 1. On cible les divs qui ont la classe 'bloc' (les capsules)
    blocs = soup.find_all('div', class_='bloc')
    
    for bloc in blocs:
        bloc_id = bloc.get('id')
        # Exclure les blocs d'en-tête de colonnes
        if not bloc_id or 'haut' in bloc.get('class', []):
            continue
            
        # Extraction du titre
        titre_div = bloc.find('div', class_='titre')
        if not titre_div:
            continue
        titre = titre_div.text.strip().upper() if titre_div.text.strip() else "SANS_NOM"
        
        # Extraction du nom de la colonne parente pour le dossier
        col_name = "SANS_DOSSIER"
        colonne = bloc.find_parent(class_='colonne')
        if colonne:
            haut = colonne.find(class_='haut')
            if haut:
                t = haut.find(class_='titre-colonne')
                if t: col_name = t.text.strip().upper()
        
        # Extraction du lien ou de l'image de couverture
        a_tag = bloc.find('a', href=True)
        img_tag = bloc.find('img', src=True)
        
        # Vérifier l'icône pour détecter les documents (PDF)
        media_type_span = bloc.find('span', class_='media-type')
        is_document = False
        if media_type_span:
            icon_tag = media_type_span.find('i', class_='material-icons')
            if icon_tag and 'description' in icon_tag.text:
                is_document = True
                
        dl_url = None
        fallback_url = None
        
        # Logique pour les liens Nuage (Lecture seule)
        if a_tag and "/s/" in a_tag.get('href', ''):
            file_id = a_tag['href'].split("/s/")[-1]
            dl_url = f"https://nuage02.apps.education.fr/public.php/dav/files/{file_id}"
            
        # Logique pour les images/fichiers S3 (Direct)
        elif img_tag and "s3.sbg.io.cloud.ovh.net" in img_tag.get('src', ''):
            src = img_tag['src']
            
            dl_url = src
            fallback_url = None
            
        if dl_url:
            resources_dict[bloc_id] = {'titre': titre, 'url': dl_url, 'fallback_url': fallback_url, 'colonne': col_name}
            
    # 2. On cible les fenêtres ouvertes (jsPanel) pour récupérer le VRAI lien
    panels = soup.find_all('div', class_='jsPanel')
    for panel in panels:
        panel_id = panel.get('id', '')
        if panel_id.startswith('panneau_'):
            bloc_id = panel_id.replace('panneau_', '')
            
            # Chercher le bouton de téléchargement avec la classe 'telecharger'
            dl_link = panel.find('a', class_='telecharger')
            iframe = panel.find('iframe')
            real_url = None
            
            if dl_link and dl_link.get('href'):
                real_url = dl_link.get('href')
            elif iframe and iframe.get('src') and 'file=' in iframe.get('src'):
                match = re.search(r'file=([^&]+)', iframe['src'])
                if match:
                    real_url = urllib.parse.unquote(match.group(1))
                    
            if real_url:
                if bloc_id in resources_dict:
                    # On remplace l'url devinée par la VRAIE url du pdf
                    resources_dict[bloc_id]['url'] = real_url
                    resources_dict[bloc_id]['fallback_url'] = None
                else:
                    titre_div = panel.find('div', class_='jsPanel-title')
                    titre = titre_div.text.strip().upper() if titre_div else "SANS_NOM"
                    resources_dict[bloc_id] = {'titre': titre, 'url': real_url, 'fallback_url': None, 'colonne': 'Fichiers_Trouves'}

    # 3. Extraction "Brute-Force" via Regex dans tout le code HTML
    # Digipad cache les vrais liens des documents. Si la page n'a pas été cliquée/rendue, 
    # ils sont quand même dans le code source (dans l'état JSON de Vue.js).
    html_clean = html_content.replace('\\/', '/')
    
    # Extraire les vrais documents S3
    doc_exts = r'\.(?:pdf|docx?|xlsx?|pptx?|odt|ods|odp|zip|rar|txt|csv)'
    doc_pattern = r'(https://digipad\.s3\.sbg\.io\.cloud\.ovh\.net/[0-9a-zA-Z_-]+/[0-9a-zA-Z_-]+' + doc_exts + ')'
    all_doc_urls = re.findall(doc_pattern, html_clean, flags=re.IGNORECASE)
    
    # Extraire les liens "Nuage" cachés
    nuage_pattern = r'(https://nuage02\.apps\.education\.fr/index\.php/s/[a-zA-Z0-9]+)'
    all_nuage_urls = re.findall(nuage_pattern, html_clean, flags=re.IGNORECASE)
    
    existing_urls = set(res['url'] for res in resources_dict.values() if res['url'])
    
    for url in set(all_doc_urls):
        if url not in existing_urls:
            filename = url.split('/')[-1]
            title = urllib.parse.unquote(filename).rsplit('.', 1)[0]
            clean_title = title.replace('_', ' ').replace('-', ' ').title()
            resources_dict[url] = {'titre': f"📄 {clean_title} (Fichier caché)", 'url': url, 'fallback_url': None, 'colonne': 'Fichiers_Caches'}
            
    for url in set(all_nuage_urls):
        file_id = url.split("/s/")[-1]
        dl_url = f"https://nuage02.apps.education.fr/public.php/dav/files/{file_id}"
        if dl_url not in existing_urls:
            resources_dict[dl_url] = {'titre': f"☁️ Nuage Caché ({file_id})", 'url': dl_url, 'fallback_url': None, 'colonne': 'Fichiers_Caches'}

    return list(resources_dict.values())


def get_resources_from_url(url, password=None):
    """
    Ouvre un navigateur Chrome invisible via Selenium pour charger dynamiquement
    le Digipad, contourner les protections, gérer les mots de passe et extraire les PDF.
    """
    chrome_options = Options()
    # Retour au mode invisible pour ne pas polluer l'écran
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    try:
        # Initialisation du navigateur Chrome
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Petit hack Javascript pour masquer totalement Selenium aux yeux du site
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                  get: () => undefined
                })
            """
        })
        
        driver.get(url)
        
        # Vérifier si un mot de passe est demandé
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password'], div.bloc"))
            )
        except Exception:
            pass
            
        password_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
        if password_inputs:
            if not password:
                driver.quit()
                return {"error": "PASSWORD_REQUIRED"}
            else:
                password_inputs[0].send_keys(password)
                password_inputs[0].send_keys(Keys.RETURN)
                time.sleep(3) # Attente de la validation
                
                # Si le mot de passe est toujours là, c'est qu'il est incorrect
                if driver.find_elements(By.CSS_SELECTOR, "input[type='password']"):
                    driver.quit()
                    return {"error": "INVALID_PASSWORD"}
        
        # Attendre que les blocs de capsules se chargent
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.bloc"))
            )
        except TimeoutException:
            driver.quit()
            return {"error": "TIMEOUT"}
            
        time.sleep(1) # Rendu final
        
        # Extraire les vrais liens en cliquant séquentiellement via un script JS injecté
        driver.set_script_timeout(180) # Autoriser jusqu'à 3 minutes pour scanner tout le Digipad
        js_script = """
        var done = arguments[arguments.length - 1];
        var results = [];
        var blocs = Array.from(document.querySelectorAll('div.bloc:not(.haut)'));
        
        async function process() {
            for (let b of blocs) {
                if (!b.id) continue;
                
                let titleEl = b.querySelector('.titre');
                let title = titleEl ? titleEl.textContent.trim().toUpperCase() : "SANS_NOM";
                
                let colNode = b.closest('.colonne');
                let colTitle = "SANS_DOSSIER";
                if (colNode) {
                    let titreCol = colNode.querySelector('.bloc.haut .titre-colonne');
                    if (titreCol) colTitle = titreCol.textContent.trim().toUpperCase();
                }
                
                let fallbackUrl = null;
                let realUrl = null;
                
                let aTag = b.querySelector('a');
                if (aTag && aTag.href.includes('/s/')) {
                    let parts = aTag.href.split('/s/');
                    let fileId = parts[parts.length - 1];
                    realUrl = "https://nuage02.apps.education.fr/public.php/dav/files/" + fileId;
                } else {
                    let imgTag = b.querySelector('img.vignette');
                    if (imgTag && imgTag.src.includes('s3.sbg.io.cloud.ovh.net')) {
                        fallbackUrl = imgTag.src;
                    }
                }
                
                // Si c'est un fichier hébergé sur Digipad, on clique pour révéler le PDF
                if (!realUrl) {
                    try {
                        // IMPORTANT : Digipad n'ouvre le PDF que si on clique sur l'image ou le bouton de l'image
                        let clickable = b.querySelector('.media span[role="button"], .media img, .media a');
                        if (clickable) {
                            clickable.click();
                        } else {
                            b.click();
                        }
                        
                        let panelId = 'panneau_' + b.id;
                        let panel = null;
                        
                        // On attend jusqu'à 1.5 seconde que la fenêtre s'ouvre
                        for(let i=0; i<15; i++) {
                            panel = document.getElementById(panelId);
                            if (panel) break;
                            await new Promise(r => setTimeout(r, 100));
                        }
                        
                        if (panel) {
                            // On attend jusqu'à 2 secondes que l'iframe ou le bouton soit généré dans la fenêtre
                            for(let i=0; i<20; i++) {
                                let link = panel.querySelector('a.telecharger');
                                if (link && link.href && !link.href.endsWith('#')) {
                                    realUrl = link.href; break;
                                }
                                let iframe = panel.querySelector('iframe');
                                if (iframe && iframe.src && iframe.src.includes('file=')) {
                                    let match = iframe.src.match(/file=([^&]+)/);
                                    if (match) { realUrl = decodeURIComponent(match[1]); break; }
                                }
                                await new Promise(r => setTimeout(r, 100));
                            }
                            let closeBtn = panel.querySelector('.jsPanel-btn-close');
                            if (closeBtn) closeBtn.click();
                            await new Promise(r => setTimeout(r, 200)); // Attente fermeture panneau
                        }
                    } catch(e) {}
                }
                
                if (realUrl || fallbackUrl) {
                    results.push({
                        titre: title,
                        url: realUrl || fallbackUrl,
                        fallback_url: fallbackUrl,
                        colonne: colTitle
                    });
                }
            }
            done(results);
        }
        process();
        """
        
        resources = driver.execute_async_script(js_script)
        
        digipad_title = driver.title.replace(' - Digipad by La Digitale', '').strip()
        digipad_title = re.sub(r'[\\/*?:"<>|]', "", digipad_title)
        if not digipad_title:
            digipad_title = "digipad_archive"
            
        driver.quit()
        
        return {'resources': resources, 'title': digipad_title}
        
    except Exception as e:
        print(f"Erreur lors de la récupération de l'URL : {e}")
        try:
            driver.quit()
        except:
            pass
        return []


@app.route('/')
def index():
    return render_template('index.html')


def verify_link_health(res):
    """ 
    Vérifie si les liens hébergés (notamment sur Nuage) sont 
    encore vivants avant de les proposer au téléchargement.
    """
    res['is_dead'] = False
    url = res.get('url')
    if url and "dav/files" in url:
        try:
            resp = requests.get(url, stream=True, timeout=7)
            # Gérer les erreurs HTTP directes (404, 403, etc.)
            if resp.status_code != 200:
                res['is_dead'] = True
                resp.close()
                return res

            # Gérer les "soft errors" (page d'erreur avec un statut 200)
            chunk = next(resp.iter_content(chunk_size=1024))
            if b"Ce partage n'existe pas" in chunk or b"Partage non trouv" in chunk:
                res['is_dead'] = True
            resp.close()
        except Exception:
            res['is_dead'] = True
    return res


@app.route('/index-page', methods=['POST'])
def index_page():
    """Route principale pour l'analyse d'une URL ou de code source HTML."""
    data = request.json
    url = data.get('url')
    html_source = data.get('html_source')
    password = data.get('password')
    
    digipad_title = "digipad_archive"
    
    if html_source and html_source.strip():
        soup = BeautifulSoup(html_source, 'html.parser')
        title_meta = soup.find('meta', property='og:title')
        if title_meta and title_meta.get('content'):
            digipad_title = title_meta['content'].replace(' - Digipad by La Digitale', '').strip()
            digipad_title = re.sub(r'[\\/*?:"<>|]', "", digipad_title)
        if not digipad_title:
            digipad_title = "digipad_archive"
            
        resources = extract_resources(html_source)
        res_data = {'resources': resources, 'title': digipad_title}
    elif url and url.strip():
        res = get_resources_from_url(url, password)
        if isinstance(res, dict) and "error" in res:
            return jsonify(res), 400
        res_data = res
    else:
        res_data = {'resources': [], 'title': digipad_title}
        
    # Vérification asynchrone de la santé des liens pour l'interface
    if res_data.get('resources'):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            res_data['resources'] = list(executor.map(verify_link_health, res_data['resources']))
            
    return jsonify(res_data)


@app.route('/download-zip', methods=['POST'])
def download_zip():
    """Télécharge les ressources sélectionnées et génère une archive ZIP."""
    items = request.json.get('items', [])
    title = request.json.get('title', 'digipad_archive')
    memory_file = io.BytesIO()
    
    def fetch_file(item):
        try:
            url = item['url']
            fallback = item.get('fallback_url')
            resp = requests.get(url, timeout=20)
            if resp.status_code != 200 and fallback:
                url = fallback
                resp = requests.get(url, timeout=20)
            if resp.status_code == 200:
                clean_title = re.sub(r'[\\/*?:"<>|]', "", item['titre'])
                if not clean_title: clean_title = "Fichier_sans_nom"
                
                # Nettoyage du nom du dossier
                clean_col = re.sub(r'[\\/*?:"<>|]', "", item.get('colonne', 'Sans_dossier')).strip()
                if not clean_col: clean_col = "Sans_dossier"
                
                # Vérifier si c'est une page d'erreur Nuage (même avec un code 200)
                if b"Ce partage n'existe pas" in resp.content or b"Partage non trouv" in resp.content:
                    return (f"{clean_col}/{clean_title}_INTROUVABLE.txt", "Ce partage n'existe pas ou n'est plus disponible.".encode('utf-8'))
                    
                if resp.status_code == 200:
                    if "dav/files" in url: ext = ".pdf"
                    else:
                        ext = os.path.splitext(url.split('?')[0])[1]
                        if not ext: ext = ".pdf"
                    return (f"{clean_col}/{clean_title}{ext}", resp.content)
                else:
                    return (f"{clean_col}/{clean_title}_ERREUR.txt", f"Erreur de telechargement: statut {resp.status_code}".encode('utf-8'))
        except Exception as e:
            print(f"Erreur téléchargement {item['url']} : {e}")
        return None

    # Téléchargement multithreadé (ultra rapide)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_file, items))
        
    # Écriture dans le Zip
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for res in results:
            if res:
                zf.writestr(res[0], res[1])
                
    memory_file.seek(0)
    return send_file(memory_file, download_name=f'{title}.zip', as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)