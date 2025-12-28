#!/usr/bin/env python3
"""
Indexerr - Jackett-compatible API for multiple torrent indexers
"""
from flask import Flask, request, jsonify, Response
from typing import List, Dict, Any
from lxml import etree as ET

from utils import load_config, get_enabled_indexers
from indexers import DonTorrentIndexer
from models import TorrentResult


app = Flask(__name__)

# Load configuration
config = load_config('config.yaml')
server_config = config.get('server', {})

# Available indexers mapping
INDEXER_CLASSES = {
    'dontorrent': DonTorrentIndexer,
    # You can add more indexers in the future:
    # 'otro_indexer': OtroIndexerClass,
}

# Instanciar indexers habilitados
indexers: Dict[str, Any] = {}
enabled_indexers = get_enabled_indexers(config)

for name, indexer_config in enabled_indexers.items():
    if name in INDEXER_CLASSES:
        try:
            indexers[name] = INDEXER_CLASSES[name](indexer_config)
            print(f"✓ Indexer '{name}' cargado correctamente")
        except Exception as e:
            print(f"✗ Error cargando indexer '{name}': {e}")
    else:
        print(f"⚠ Indexer '{name}' no tiene clase implementada")


@app.route('/')
def index():
    """Root endpoint with service information"""
    return jsonify({
        'name': 'Indexerr',
        'version': '1.0.0',
        'description': 'Jackett-compatible API for multiple indexers',
        'indexers_enabled': list(indexers.keys()),
        'endpoints': {
            'search_all': '/api/v1/search?q=query',
            'search_indexer': '/api/v1/indexers/<indexer>/results?q=query',
            'tvsearch': '/api/v1/indexers/<indexer>/tvsearch?q=series&season=1&ep=1',
            'indexers': '/api/v1/indexers',
            'test': '/api/v1/test',
        }
    })


@app.route('/api/v1/indexers')
def list_indexers():
    """Lista los indexers habilitados"""
    indexer_info = []
    
    for name, indexer in indexers.items():
        indexer_info.append({
            'id': name,
            'name': indexer.name,
            'domain': indexer.domain,
            'enabled': indexer.enabled,
        })
    
    return jsonify({
        'indexers': indexer_info,
        'count': len(indexer_info)
    })


@app.route('/api/v1/test')
def test_indexers():
    """Test connection to all indexers"""
    results = {}
    
    for name, indexer in indexers.items():
        try:
            is_ok = indexer.test_connection()
            results[name] = {
                'status': 'ok' if is_ok else 'error',
                'domain': indexer.domain
            }
        except Exception as e:
            results[name] = {
                'status': 'error',
                'error': str(e)
            }
    
    return jsonify(results)


@app.route('/api/v1/search')
def search_all():
    """
    Busca torrents en todos los indexers habilitados (Torznab compatible)
    
    Query params:
        q: Search term (requerido)
        t: Search type (optional, for Torznab compatibility)
        cat: Categories (optional, for Torznab compatibility)
    
    Returns:
        JSON con resultados en formato Jackett
    """
    # Validate Torznab parameters
    VALID_SEARCH_PARAMS = {'q', 't', 'cat', 'limit', 'offset'}
    provided_params = set(request.args.keys())
    invalid_params = provided_params - VALID_SEARCH_PARAMS
    
    if invalid_params:
        return jsonify({
            'error': f'Unsupported parameters: {", ".join(sorted(invalid_params))}',
            'valid_params': sorted(list(VALID_SEARCH_PARAMS))
        }), 400
    
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({
            'error': 'Parameter "q" is required'
        }), 400
    
    # Search all indexers
    all_results: List[TorrentResult] = []
    errors = {}
    
    for name, indexer in indexers.items():
        try:
            results = indexer.search(query)
            all_results.extend(results)
        except Exception as e:
            errors[name] = str(e)
    
    # Convertir a formato Jackett y agregar URL base al Link
    base_url = request.url_root.rstrip('/')
    jackett_results = []
    
    for r in all_results:
        result_dict = r.to_jackett_format()
        # If link is relative, convert to absolute
        if result_dict['Link'].startswith('/'):
            result_dict['Link'] = base_url + result_dict['Link']
        jackett_results.append(result_dict)
    
    response = {
        'Results': jackett_results,
        'NumberOfResults': len(jackett_results),
        'Query': query,
    }
    
    if errors:
        response['Errors'] = errors
    
    return jsonify(response)


@app.route('/api/v1/indexers/<indexer_name>/tvsearch')
def tvsearch_indexer(indexer_name: str):
    """
    Busca episodios de series (Torznab tvsearch compatible)
    
    Args:
        indexer_name: Nombre del indexer
    
    Query params:
        q: Series name (requerido)
        season: Season number (opcional)
        ep: Episode number (opcional)
    
    Returns:
        JSON con episodios individuales en formato Jackett
    """
    # Validate Torznab parameters
    VALID_TVSEARCH_PARAMS = {'q', 'season', 'ep', 'tvdbid', 'rid', 'imdbid'}
    provided_params = set(request.args.keys())
    invalid_params = provided_params - VALID_TVSEARCH_PARAMS
    
    if invalid_params:
        return jsonify({
            'error': f'Unsupported parameters: {", ".join(sorted(invalid_params))}',
            'valid_params': sorted(list(VALID_TVSEARCH_PARAMS)),
            'hint': 'Use "ep" instead of "episode" (Torznab standard)'
        }), 400
    
    series_name = request.args.get('q', '').strip()
    season = request.args.get('season', '').strip()
    episode = request.args.get('ep', '').strip()
    
    if not series_name:
        return jsonify({
            'error': 'Parameter "q" (series name) is required'
        }), 400
    
    # Verify indexer exists
    if indexer_name not in indexers:
        return jsonify({
            'error': f'Indexer "{indexer_name}" no encontrado o no habilitado',
            'available_indexers': list(indexers.keys())
        }), 404
    
    indexer = indexers[indexer_name]
    
    # Verify indexer supports episode search
    if not hasattr(indexer, 'search_episodes'):
        return jsonify({
            'error': f'Indexer "{indexer_name}" does not support episode search'
        }), 501
    
    # Convert season and episode to int if present
    season_int = int(season) if season.isdigit() else None
    episode_int = int(episode) if episode.isdigit() else None
    
    try:
        results = indexer.search_episodes(series_name, season_int, episode_int)
        
        # Convertir a formato Jackett y agregar URL base al Link
        base_url = request.url_root.rstrip('/')
        jackett_results = []
        
        for r in results:
            result_dict = r.to_jackett_format()
            # If link is relative, convert to absolute
            if result_dict['Link'].startswith('/'):
                result_dict['Link'] = base_url + result_dict['Link']
            
            # Add TV attributes
            if season_int:
                result_dict['Season'] = season_int
            if episode_int:
                result_dict['Episode'] = episode_int
            
            jackett_results.append(result_dict)
        
        return jsonify({
            'Results': jackett_results,
            'NumberOfResults': len(jackett_results),
            'Query': series_name,
            'Season': season_int,
            'Episode': episode_int,
            'Indexer': indexer_name
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'indexer': indexer_name
        }), 500


@app.route('/api/v1/indexers/<indexer_name>/api')
def torznab_api(indexer_name: str):
    """
    Torznab API endpoint (caps, search, tvsearch)
    
    Args:
        indexer_name: Indexer name
        
    Query params:
        t: Type of request (caps, search, tvsearch)
    """
    t = request.args.get('t', '').lower()
    
    # Verify indexer exists
    if indexer_name not in indexers:
        return jsonify({
            'error': f'Indexer "{indexer_name}" not found or not enabled',
            'available_indexers': list(indexers.keys())
        }), 404
    
    # Handle caps request - return XML for Torznab compatibility
    if t == 'caps':
        caps = ET.Element('caps')
        
        server = ET.SubElement(caps, 'server')
        server.set('title', 'Indexarr')
        server.set('version', '1.0')
        
        searching = ET.SubElement(caps, 'searching')
        
        search = ET.SubElement(searching, 'search')
        search.set('available', 'yes')
        search.set('supportedParams', 'q')
        
        tv_search = ET.SubElement(searching, 'tv-search')
        tv_search.set('available', 'yes')
        tv_search.set('supportedParams', 'q,season,ep')
        
        movie_search = ET.SubElement(searching, 'movie-search')
        movie_search.set('available', 'yes')
        movie_search.set('supportedParams', 'q')
        
        categories = ET.SubElement(caps, 'categories')
        
        cat_movies = ET.SubElement(categories, 'category')
        cat_movies.set('id', '2000')
        cat_movies.set('name', 'Movies')
        
        cat_tv = ET.SubElement(categories, 'category')
        cat_tv.set('id', '5000')
        cat_tv.set('name', 'TV')
        
        xml_string = ET.tostring(caps, encoding='utf-8', xml_declaration=True, pretty_print=True)
        return Response(xml_string, mimetype='application/xml')
    
    # Handle search request - return XML RSS
    elif t == 'search' or t == 'tvsearch':
        indexer = indexers[indexer_name]
        
        # Get query parameters
        query = request.args.get('q', '')
        season = request.args.get('season')
        ep = request.args.get('ep')
        limit = request.args.get('limit', type=int, default=100)
        offset = request.args.get('offset', type=int, default=0)
        
        # If no query provided, use a generic search term to get recent results
        if not query:
            # For test/capability checks, return recent popular content
            query = 'the'  # Generic search that will return some results
        
        # Perform search based on type
        if t == 'tvsearch' and hasattr(indexer, 'search_episodes'):
            try:
                season_int = int(season) if season else None
                ep_int = int(ep) if ep else None
            except (ValueError, TypeError):
                season_int = None
                ep_int = None
            
            results = indexer.search_episodes(query, season_int, ep_int)
        else:
            results = indexer.search(query)
        
        # Apply pagination
        total_results = len(results)
        results = results[offset:offset + limit]
        
        # Build Torznab XML RSS response with namespaces
        TORZNAB_NS = 'http://torznab.com/schemas/2015/feed'
        ATOM_NS = 'http://www.w3.org/2005/Atom'
        
        nsmap = {
            'torznab': TORZNAB_NS,
            'atom': ATOM_NS
        }
        
        rss = ET.Element('rss', nsmap=nsmap, version='2.0')
        
        channel = ET.SubElement(rss, 'channel')
        
        title = ET.SubElement(channel, 'title')
        title.text = f'Indexarr - {indexer_name}'
        
        description = ET.SubElement(channel, 'description')
        description.text = f'Search results for {query}' if query else 'Search results'
        
        link = ET.SubElement(channel, 'link')
        link.text = request.host_url
        
        # Torznab response element with pagination info
        response_elem = ET.SubElement(channel, f'{{{TORZNAB_NS}}}response')
        response_elem.set('offset', str(offset))
        response_elem.set('total', str(total_results))
        
        # Add items
        for result in results:
            item = ET.SubElement(channel, 'item')
            
            item_title = ET.SubElement(item, 'title')
            item_title.text = result.title
            
            item_guid = ET.SubElement(item, 'guid', isPermaLink='false')
            item_guid.text = result.guid
            
            # Make link absolute if relative
            if result.link.startswith('http'):
                download_url = result.link
            else:
                download_url = request.host_url.rstrip('/') + result.link
            
            item_link = ET.SubElement(item, 'link')
            item_link.text = download_url
            
            # Add enclosure for torrent file (required by some clients)
            enclosure = ET.SubElement(item, 'enclosure')
            enclosure.set('url', download_url)
            enclosure.set('length', str(result.size if result.size else 0))
            enclosure.set('type', 'application/x-bittorrent')
            
            item_details = ET.SubElement(item, 'comments')
            item_details.text = result.details_url
            
            # pubDate is REQUIRED by RSS 2.0
            item_pubdate = ET.SubElement(item, 'pubDate')
            if result.publish_date:
                item_pubdate.text = result.publish_date.strftime('%a, %d %b %Y %H:%M:%S +0000')
            else:
                # Use current time if not available
                from datetime import datetime
                item_pubdate.text = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')
            
            # Torznab attributes
            if result.size:
                size_attr = ET.SubElement(item, f'{{{TORZNAB_NS}}}attr')
                size_attr.set('name', 'size')
                size_attr.set('value', str(result.size))
            
            # Category as torznab attributes
            if result.category:
                # Map Spanish categories to Torznab IDs
                category_map = {
                    'Películas': [2000],
                    'Movies': [2000],
                    'Series': [5000],
                    'Documentales': [7000],
                    'Documentaries': [7000]
                }
                cat_ids = category_map.get(result.category, [8000])
                for cat_id in cat_ids:
                    cat_attr = ET.SubElement(item, f'{{{TORZNAB_NS}}}attr')
                    cat_attr.set('name', 'category')
                    cat_attr.set('value', str(cat_id))
            
            if result.seeders is not None:
                seeders_attr = ET.SubElement(item, f'{{{TORZNAB_NS}}}attr')
                seeders_attr.set('name', 'seeders')
                seeders_attr.set('value', str(result.seeders))
            
            if result.leechers is not None:
                peers_attr = ET.SubElement(item, f'{{{TORZNAB_NS}}}attr')
                peers_attr.set('name', 'peers')
                peers_attr.set('value', str(result.leechers))
            
            # TV specific attributes
            if hasattr(result, 'season') and result.season is not None:
                season_attr = ET.SubElement(item, f'{{{TORZNAB_NS}}}attr')
                season_attr.set('name', 'season')
                season_attr.set('value', str(result.season))
            
            if hasattr(result, 'episode') and result.episode is not None:
                ep_attr = ET.SubElement(item, f'{{{TORZNAB_NS}}}attr')
                ep_attr.set('name', 'episode')
                ep_attr.set('value', str(result.episode))
        
        xml_string = ET.tostring(rss, encoding='utf-8', xml_declaration=True, pretty_print=True)
        return Response(xml_string, mimetype='application/rss+xml')
    
    else:
        # Return error as XML
        error = ET.Element('error')
        error.set('code', '203')
        error.set('description', f'Unknown request type: {t}')
        xml_string = ET.tostring(error, encoding='utf-8', xml_declaration=True)
        return Response(xml_string, mimetype='application/xml'), 400


@app.route('/api/v1/indexers/<indexer_name>/results')
def search_indexer(indexer_name: str):
    """
    Search torrents in specific indexer (Torznab compatible)
    
    Args:
        indexer_name: Nombre del indexer
    
    Query params:
        q: Search term (requerido)
        t: Search type (optional, for Torznab compatibility)
        cat: Categories (optional, for Torznab compatibility)
    
    Returns:
        JSON con resultados en formato Jackett
    """
    # Validate Torznab parameters
    VALID_SEARCH_PARAMS = {'q', 't', 'cat', 'limit', 'offset'}
    provided_params = set(request.args.keys())
    invalid_params = provided_params - VALID_SEARCH_PARAMS
    
    if invalid_params:
        return jsonify({
            'error': f'Unsupported parameters: {", ".join(sorted(invalid_params))}',
            'valid_params': sorted(list(VALID_SEARCH_PARAMS))
        }), 400
    
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({
            'error': 'Parameter "q" is required'
        }), 400
    
    # Verify indexer exists
    if indexer_name not in indexers:
        return jsonify({
            'error': f'Indexer "{indexer_name}" no encontrado o no habilitado',
            'available_indexers': list(indexers.keys())
        }), 404
    
    # Search in specific indexer
    indexer = indexers[indexer_name]
    
    try:
        results = indexer.search(query)
        
        # Convertir a formato Jackett y agregar URL base al Link
        base_url = request.url_root.rstrip('/')
        jackett_results = []
        
        for r in results:
            result_dict = r.to_jackett_format()
            # If link is relative, convert to absolute
            if result_dict['Link'].startswith('/'):
                result_dict['Link'] = base_url + result_dict['Link']
            jackett_results.append(result_dict)
        
        return jsonify({
            'Results': jackett_results,
            'NumberOfResults': len(jackett_results),
            'Query': query,
            'Indexer': indexer_name
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'indexer': indexer_name
        }), 500


@app.route('/api/v1/indexers/<indexer_name>/download')
def download(indexer_name: str):
    """
    Obtiene el archivo .torrent directamente (hace PoW si es necesario)
    
    Args:
        indexer_name: Nombre del indexer
        
    Query params:
        url: Detail page URL del torrent
        tabla: Tipo de contenido (peliculas, series, etc)
    
    Returns:
        Redirect to file .torrent o JSON con la URL
    """
    if indexer_name not in indexers:
        return jsonify({
            'error': f'Indexer "{indexer_name}" no encontrado'
        }), 404
    
    indexer = indexers[indexer_name]
    
    # For DonTorrent, get link using PoW
    if indexer_name == 'dontorrent':
        from flask import redirect
        
        detail_url = request.args.get('url')
        tabla = request.args.get('tabla', 'peliculas')
        episode_id = request.args.get('episode_id')  # Direct episode ID
        
        # If we have episode_id, use it directly (comes from tvsearch)
        if episode_id:
            content_id = episode_id
            tabla_final = tabla
            print(f"[Download] Usando episode_id directo: {content_id}")
        else:
            # If not, get from detail page (original behavior)
            if not detail_url:
                return jsonify({
                    'error': 'Parameter "url" or "episode_id" is required'
                }), 400
            
            # Get real content_id from detail page
            result = indexer.get_real_content_id(detail_url)
            
            if not result:
                return jsonify({
                    'error': 'Could not get content_id from detail page'
                }), 500
            
            content_id, real_tabla = result
            
            # Use button table if available, otherwise use parameter table
            tabla_final = real_tabla if real_tabla else tabla
        
        download_url = indexer.get_download_link(content_id, tabla_final)
        
        if download_url:
            # Redirigir directamente al .torrent
            return redirect(download_url)
        else:
            return jsonify({
                'error': 'Could not get download link after PoW'
            }), 500
    
    return jsonify({
        'error': 'Download method not implemented for this indexer'
    }), 501


if __name__ == '__main__':
    host = server_config.get('host', '0.0.0.0')
    port = server_config.get('port', 5000)
    debug = server_config.get('debug', False)
    
    print(f"\n{'='*60}")
    print(f"Indexerr API Server")
    print(f"{'='*60}")
    print(f"Indexers habilitados: {', '.join(indexers.keys())}")
    print(f"Servidor: http://{host}:{port}")
    print(f"{'='*60}\n")
    
    app.run(host=host, port=port, debug=debug)
