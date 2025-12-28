import hashlib
import json
import time
from typing import List, Optional
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from titlecase import titlecase

from .base import BaseIndexer
from models import TorrentResult


class DonTorrentIndexer(BaseIndexer):
    """DonTorrent indexer with Proof of Work support"""
    
    @property
    def name(self) -> str:
        return "DonTorrent"
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        })
    
    def search(self, query: str) -> List[TorrentResult]:
        """
        Search torrents on DonTorrent using the site search
        
        Args:
            query: Search term
            
        Returns:
            List of TorrentResult
        """
        results = []
        
        try:
            # POST to /buscar
            search_url = urljoin(self.domain, '/buscar')
            data = {'valor': query}
            
            response = self.session.post(search_url, data=data, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Results are in paragraphs within the results section
            # Format: <p><span><a href="/pelicula/ID/nombre">Title</a> (Calidad) <span>Tipo</span></span></p>
            paragraphs = soup.find_all('p')
            
            for p in paragraphs:
                # Find link inside paragraph
                link = p.find('a', href=True)
                if not link:
                    continue
                
                href = link.get('href')
                
                # Verify it is a valid link
                if not (href.startswith('/pelicula/') or 
                        href.startswith('/serie/') or 
                        href.startswith('/documental/')):
                    continue
                
                # Get title from link
                title = link.get_text(strip=True)
                if not title:
                    continue
                
                # Extract quality from text (e.g.: "(BluRay-1080p)")
                quality = ''
                p_text = p.get_text()
                if '(' in p_text and ')' in p_text:
                    quality = p_text[p_text.find('(')+1:p_text.find(')')]
                
                # Determine category based on span type
                category = 'Desconocido'
                tipo_span = p.find('span')
                if tipo_span:
                    tipo_text = tipo_span.get_text(strip=True).lower()
                    if 'movie' in tipo_text or 'pelicula' in tipo_text:
                        category = 'Movies'
                    elif 'serie' in tipo_text:
                        category = 'Series'
                    elif 'documental' in tipo_text:
                        category = 'Documentales'
                
                # Build complete URL
                detail_url = urljoin(self.domain, href)
                
                # Extract ID from href
                parts = href.strip('/').split('/')
                if len(parts) >= 2:
                    content_id = parts[1]
                else:
                    continue
                
                # Add quality to title if exists
                full_title = f"{title} [{quality}]" if quality else title
                
                # Determine table based on content type
                tabla = 'peliculas'
                if href.startswith('/serie/'):
                    tabla = 'series'
                elif href.startswith('/documental/'):
                    tabla = 'documentales'
                
                # For series and documentaries, the real content_id is on the detail page
                # For now, create a special link that includes the full URL
                # The download endpoint will extract the real content_id
                download_link = f"/api/v1/indexers/dontorrent/download?url={detail_url}&tabla={tabla}"
                
                result = TorrentResult(
                    title=full_title,
                    guid=f"dontorrent-{content_id}",
                    link=download_link,  # Link to download endpoint
                    details_url=detail_url,  # Link to details page
                    indexer=self.name,
                    category=category,
                )
                
                results.append(result)
        
        except Exception as e:
            print(f"Error buscando en DonTorrent: {e}")
            import traceback
            traceback.print_exc()
        
        return results
    
    def get_download_link(self, content_id: str, tabla: str = 'peliculas') -> Optional[str]:
        """
        Obtiene el enlace de descarga usando el sistema PoW
        
        Args:
            content_id: ID del contenido
            tabla: Tipo de contenido (peliculas, series, etc)
            
        Returns:
            URL de descarga del torrent o None si falla
        """
        try:
            print(f"[PoW] Starting download for content_id={content_id}, tabla={tabla}")
            
            # Paso 1: Generar challenge
            generate_url = urljoin(self.domain, '/api_validate_pow.php')
            generate_payload = {
                'action': 'generate',
                'content_id': int(content_id),
                'tabla': tabla
            }
            
            print(f"[PoW] Generating challenge at {generate_url}")
            print(f"[PoW] Payload: {generate_payload}")
            
            response = self.session.post(
                generate_url,
                json=generate_payload,
                timeout=self.timeout
            )
            
            print(f"[PoW] Status code: {response.status_code}")
            print(f"[PoW] Response: {response.text[:500]}")
            
            if not response.ok:
                print(f"[PoW ERROR] Error generating challenge: {response.status_code}")
                print(f"[PoW ERROR] Response body: {response.text}")
                return None
            
            data = response.json()
            print(f"[PoW] Response JSON: {data}")
            
            if not data.get('success'):
                print(f"[PoW ERROR] Error in response: {data.get('error')}")
                return None
            
            challenge = data.get('challenge')
            print(f"[PoW] Challenge obtained: {challenge}")
            
            # Paso 2: Calcular Proof of Work
            nonce = self._compute_proof_of_work(challenge, difficulty=3)
            
            # Step 3: Validate with server
            validate_payload = {
                'action': 'validate',
                'challenge': challenge,
                'nonce': nonce
            }
            
            print(f"[PoW] Validating with nonce={nonce}")
            
            response = self.session.post(
                generate_url,
                json=validate_payload,
                timeout=self.timeout
            )
            
            print(f"[PoW] Validation status: {response.status_code}")
            
            if not response.ok:
                print(f"[PoW ERROR] Error validating PoW: {response.status_code}")
                print(f"[PoW ERROR] Response: {response.text}")
                return None
            
            data = response.json()
            print(f"[PoW] Validation response: {data}")
            
            if data.get('success'):
                download_url = data.get('download_url')
                print(f"[PoW SUCCESS] Download URL: {download_url}")
                return download_url
            else:
                print(f"[PoW ERROR] Validation failed: {data.get('error')}")
                return None
                
        except Exception as e:
            print(f"[PoW EXCEPTION] Error getting download link: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _compute_proof_of_work(self, challenge: str, difficulty: int = 3) -> int:
        """
        Calculate Proof of Work (find a nonce that produces a valid hash)
        
        Args:
            challenge: Server challenge string
            difficulty: Number of leading zeros required in hash
            
        Returns:
            Nonce that solves the challenge
        """
        target = '0' * difficulty
        nonce = 0
        
        print(f"Calculando PoW (difficulty={difficulty})...")
        start_time = time.time()
        
        while True:
            text = f"{challenge}{nonce}"
            hash_hex = hashlib.sha256(text.encode()).hexdigest()
            
            if hash_hex.startswith(target):
                elapsed = time.time() - start_time
                print(f"PoW resuelto: nonce={nonce} en {elapsed:.2f}s")
                return nonce
            
            nonce += 1
            
            # Progress log every 10000 attempts
            if nonce % 10000 == 0:
                print(f"  Intentos: {nonce}...")
    
    def get_real_content_id(self, detail_url: str) -> Optional[tuple]:
        """
        Get real content_id from detail page
        
        Args:
            detail_url: Detail page URL
            
        Returns:
            Tupla (content_id, tabla) o None si falla
        """
        try:
            print(f"[ContentID] Getting real content_id from: {detail_url}")
            
            response = self.session.get(detail_url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find button with data-content-id
            download_btn = soup.find(class_='protected-download')
            
            if download_btn:
                content_id = download_btn.get('data-content-id')
                tabla = download_btn.get('data-tabla')
                
                print(f"[ContentID] Found: content_id={content_id}, tabla={tabla}")
                return (content_id, tabla)
            else:
                print(f"[ContentID ERROR] Download button not found")
                return None
                
        except Exception as e:
            print(f"[ContentID EXCEPTION] Error obteniendo content_id: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def search_episodes(self, series_name: str, season: Optional[int] = None, episode: Optional[int] = None) -> List[TorrentResult]:
        """
        Search episodes of a specific series
        
        Args:
            series_name: Series name
            season: Season number (opcional)
            episode: Episode number (opcional)
            
        Returns:
            List of TorrentResult con episodios individuales
        """
        results = []
        
        # Build search query
        # If there is a season, add "- Xª Temporada" to the name
        if season:
            query = f"{series_name} - {season}ª Temporada"
        else:
            query = series_name
        
        print(f"[TVSearch] Buscando: '{query}' (season={season}, episode={episode})")
        
        try:
            # Perform search
            search_url = urljoin(self.domain, '/buscar')
            data = {'valor': query}
            
            response = self.session.post(search_url, data=data, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            paragraphs = soup.find_all('p')
            
            # Find matching series
            for p in paragraphs:
                link = p.find('a', href=True)
                if not link:
                    continue
                
                href = link.get('href')
                
                # ONLY process series (not movies or documentaries)
                if not href.startswith('/serie/'):
                    continue
                
                title = link.get_text(strip=True)
                if not title:
                    continue
                
                # Type is in a badge or span  
                # Can be in <span class="badge">Serie</span> or similar
                tipo_badge = p.find('span', class_='badge')
                tipo_span = p.find('span')
                
                # IMPORTANT: Verify it is a series (not movie or documentary)
                is_serie = False
                if tipo_badge and 'serie' in tipo_badge.get_text(strip=True).lower():
                    is_serie = True
                elif tipo_span and 'serie' in tipo_span.get_text(strip=True).lower():
                    is_serie = True
                elif 'serie' in p.get_text().lower():
                    # Fallback: verify if "Serie" appears in paragraph text
                    is_serie = True
                
                # Discard if movie or documentary
                text_p = p.get_text().lower()
                if 'movie' in text_p or 'pelicula' in text_p or 'documental' in text_p:
                    is_serie = False
                
                if not is_serie:
                    print(f"[TVSearch] Discarding (not a series): {title}")
                    continue
                
                # Build complete URL
                detail_url = urljoin(self.domain, href)
                
                print(f"[TVSearch] Found series: {title}")
                print(f"[TVSearch] URL: {detail_url}")
                
                # Go to detail page and extract episodes
                episodes = self._extract_episodes(detail_url, season, episode)
                results.extend(episodes)
        
        except Exception as e:
            print(f"[TVSearch ERROR] Error searching episodes: {e}")
            import traceback
            traceback.print_exc()
        
        return results
    
    def _extract_episodes(self, series_url: str, filter_season: Optional[int] = None, filter_episode: Optional[int] = None) -> List[TorrentResult]:
        """
        Extract episodes from series detail page
        
        Args:
            series_url: Detail page URL
            filter_season: Filter by specific season (opcional)
            filter_episode: Filter by specific episode (opcional)
            
        Returns:
            List of TorrentResult con episodios
        """
        results = []
        
        try:
            print(f"[TVSearch] Extracting episodes from: {series_url}")
            
            response = self.session.get(series_url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find episodes table
            table = soup.find('table')
            if not table:
                print(f"[TVSearch] Episodes table not found at {series_url}")
                return results
            
            # Verify there are episode rows
            rows = table.find_all('tr')
            if len(rows) <= 1:  # Only header, no episodes
                print(f"[TVSearch] Table has no episodes (only header)")
                return results
            
            # Process table rows (skip header)
            episode_rows = rows[1:]
            
            # Get series title from page
            # There are multiple h2, the series one is the second or search by context
            all_h2 = soup.find_all('h2')
            full_series_title = None
            
            # Find h2 that contains "Temporada" or use the second
            for h2 in all_h2:
                h2_text = h2.get_text(strip=True)
                if 'Temporada' in h2_text or 'temporada' in h2_text.lower():
                    full_series_title = h2_text
                    break
            
            # If not found, try from page title
            if not full_series_title:
                page_title = soup.find('title')
                if page_title:
                    # Title: "Descargar Serie - Temporada Torrent Gratis - DonTorrent"
                    title_text = page_title.get_text(strip=True)
                    title_match = re.search(r'Descargar (.+?) Torrent', title_text)
                    if title_match:
                        full_series_title = title_match.group(1).strip()
            
            # Fallback: use second h2 if exists
            if not full_series_title and len(all_h2) > 1:
                full_series_title = all_h2[1].get_text(strip=True)
            
            # Last fallback
            if not full_series_title:
                full_series_title = "Serie"
            
            # Extract title components
            import re
            
            # Extract series name (part before " - Xª Temporada")
            series_name_match = re.match(r'^(.+?)\s*-\s*\d+ª Temporada', full_series_title)
            if series_name_match:
                series_name = series_name_match.group(1).strip()
            else:
                # Fallback: part before first " - "
                series_name_match = re.match(r'^([^-]+)', full_series_title)
                series_name = series_name_match.group(1).strip() if series_name_match else full_series_title
            
            # Extract season
            season_match = re.search(r'(\d+)ª Temporada', full_series_title)
            page_season = int(season_match.group(1)) if season_match else None
            
            # Get format/quality from page (HDTV-720p, BluRay-1080p, etc)
            # Find paragraph containing "Format:" (can be in a <b> inside the <p>)
            quality = None
            all_paragraphs = soup.find_all('p')
            for p in all_paragraphs:
                p_text = p.get_text(strip=True)
                if 'Format:' in p_text:
                    formato_match = re.search(r'Format:\s*(.+?)(?:\s|$)', p_text)
                    if formato_match:
                        quality = formato_match.group(1).strip()
                    break
            
            print(f"[TVSearch] Series: {series_name}, Season: {page_season}, Quality: {quality}, Rows: {len(episode_rows)}")
            
            for row in episode_rows:
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue
                
                # First cell: episode number (e.g.: "4x01 -" o "4x01 - Episodio en V.O. Sub Esp.")
                episode_cell = cells[0].get_text(strip=True)
                episode_cell_lower = episode_cell.lower()
                
                # ROBUST PACK DETECTION AT ROW LEVEL
                is_pack = False
                
                # 1. Search for pack text indicators
                pack_text_indicators = [' al ', ' a ', 'completa', 'todos', 'pack', 'temporada completa']
                if any(indicator in episode_cell_lower for indicator in pack_text_indicators):
                    is_pack = True
                    print(f"[TVSearch] Pack detected (text): '{episode_cell}'")
                
                # 2. Parse first episode number
                ep_match = re.match(r'(\d+)x(\d+)', episode_cell)
                if not ep_match:
                    print(f"[TVSearch] Could not parse episode: '{episode_cell}'")
                    continue
                
                # 3. Verify there is NO other episode number after (indicates range/pack)
                first_episode_end = ep_match.end()
                remaining_text = episode_cell[first_episode_end:]
                
                # Search for another XxYY in remaining text
                if re.search(r'\d+x\d+', remaining_text):
                    is_pack = True
                    print(f"[TVSearch] Pack detected (multiple episodes): '{episode_cell}'")
                
                # 4. Search for numeric range patterns (e.g.: "01-10", "1 al 10")
                if re.search(r'\d+\s*[-–—]\s*\d+', remaining_text):
                    is_pack = True
                    print(f"[TVSearch] Pack detected (numeric range): '{episode_cell}'")
                
                # FINAL DECISION:
                # - If searching for specific episode (ep != None) → ONLY episodes, discard packs
                # - If searching only by season (ep == None) → ONLY packs, discard episodes
                if filter_episode is not None:
                    # Specific episode search: discard packs
                    if is_pack:
                        print(f"[TVSearch] Discarding pack because searching for specific episode")
                        continue
                else:
                    # Season-only search: discard individual episodes
                    if not is_pack:
                        print(f"[TVSearch] Discarding individual episode because searching for season pack")
                        continue
                
                ep_season = int(ep_match.group(1))
                ep_number = int(ep_match.group(2))
                
                # Use page season if couldn't parse from episode
                if page_season:
                    ep_season = page_season
                
                # Filter by season if specified
                if filter_season is not None and ep_season != filter_season:
                    continue
                
                # Filter by episode if specified
                if filter_episode is not None and ep_number != filter_episode:
                    continue
                
                # Second cell: download button
                download_cell = cells[1]
                download_btn = download_cell.find(class_='protected-download')
                
                if not download_btn:
                    continue
                
                content_id = download_btn.get('data-content-id')
                tabla = download_btn.get('data-tabla', 'series')
                
                if not content_id:
                    continue
                
                # Third cell: date (format YYYY-MM-DD)
                publish_date = None
                if len(cells) >= 3:
                    date_cell = cells[2]
                    date_text = date_cell.get_text(strip=True)
                    # Try to parse date in format YYYY-MM-DD
                    try:
                        from datetime import datetime
                        publish_date = datetime.strptime(date_text, '%Y-%m-%d')
                    except (ValueError, AttributeError):
                        pass
                
                # Build title
                series_name_normalized = titlecase(series_name)
                
                if is_pack:
                    # Complete pack: "Serie - Temporada X Completa [Calidad]"
                    title_parts = [series_name_normalized, f"- Temporada {ep_season} Completa"]
                    if quality:
                        title_parts.append(f"[{quality}]")
                    episode_title = " ".join(title_parts)
                else:
                    # Individual episode: "Serie SXXEXX [Calidad/Formato]"
                    title_parts = [series_name_normalized]
                    title_parts.append(f"S{ep_season:02d}E{ep_number:02d}")
                    if quality:
                        title_parts.append(f"[{quality}]")
                    episode_title = " ".join(title_parts)
                
                # Create download link
                download_link = f"/api/v1/indexers/dontorrent/download?url={series_url}&tabla={tabla}&episode_id={content_id}"
                
                result = TorrentResult(
                    title=episode_title,
                    guid=f"dontorrent-episode-{content_id}",
                    link=download_link,
                    details_url=series_url,
                    indexer=self.name,
                    category="Series",
                    season=ep_season,
                    episode=ep_number if not is_pack else None,
                    publish_date=publish_date
                )
                
                print(f"[TVSearch] Episode found: {episode_title} (content_id={content_id})")
                results.append(result)
        
        except Exception as e:
            print(f"[TVSearch ERROR] Error extracting episodes: {e}")
            import traceback
            traceback.print_exc()
        
        return results
    
    def test_connection(self) -> bool:
        """Test indexer connection"""
        try:
            response = self.session.get(self.domain, timeout=10)
            return response.status_code == 200
        except:
            return False
