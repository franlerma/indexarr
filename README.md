# Indexarr

Torznab/Jackett-compatible API for Spanish torrent indexers, with support for movie and TV series search.

**Pull requests welcome!** If you want to implement support for a new indexer, feel free to contribute.

## 🚀 Features

- ✅ **Torznab/Jackett-compatible REST API**
- ✅ **Full DonTorrent support** 
- ✅ **TV series search (tvsearch)** with season and episode support
- ✅ **Intelligent pack vs individual episode detection**
- ✅ **Direct torrent downloads** without captcha solving
- ✅ **Modular architecture** for easy indexer additions
- ✅ **Docker** with Alpine Linux (~150-200MB)
- ✅ **Makefile** for simplified management

---

## 📦 Installation

### With Docker (recommended)

```bash
git clone <repo-url>
cd indexarr
make test    # First time: full rebuild
make up      # Next times: start without rebuild
```

### Manual

```bash
git clone <repo-url>
cd indexarr

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

---

## 🛠️ Makefile

| Command | Description |
|---------|-------------|
| `make up` | Start container (uses existing image) |
| `make test` | Full rebuild + start container |
| `make down` | Stop and remove container |
| `make restart` | Restart container without rebuild |
| `make logs` | View logs in real-time |
| `make clean` | Clean everything (container + image) |
| `make rebuild` | Clean and rebuild from scratch |
| `make install` | Install dependencies locally |
| `make help` | Show all available commands |

---

## 🌐 Endpoints

### Base URL
```
http://localhost:15505
```

---

### 1. **Service information**

```bash
GET /
```

**Response:**
```json
{
  "service": "Indexarr",
  "version": "1.0",
  "indexers": ["dontorrent"]
}
```

---

### 2. **List enabled indexers**

```bash
GET /api/v1/indexers
```

**Response:**
```json
{
  "indexers": ["dontorrent"],
  "count": 1
}
```

---

### 3. **Test indexer connections**

```bash
GET /api/v1/test
```

**Response:**
```json
{
  "dontorrent": {
    "status": "ok",
    "domain": "https://dontorrent.prof"
  }
}
```

---

### 4. **Search torrents (all indexers)**

```bash
GET /api/v1/search?q={query}
```

**Parameters:**
- `q` (required): Search term
- `t` (optional): Search type (Torznab)
- `cat` (optional): Categories (Torznab)
- `limit` (optional): Maximum number of results
- `offset` (optional): Pagination offset

**Example:**
```bash
curl "http://localhost:15505/api/v1/search?q=avatar"
```

**Response:**
```json
{
  "Results": [
    {
      "Title": "Avatar (2009) [BluRay-1080p]",
      "Guid": "dontorrent-12345",
      "Link": "http://localhost:15505/api/v1/indexers/dontorrent/download?url=...",
      "Details": "https://dontorrent.prof/pelicula/12345/avatar",
      "Tracker": "DonTorrent",
      "Category": "Películas"
    }
  ],
  "NumberOfResults": 1,
  "Query": "avatar",
  "Indexer": "all"
}
```

---

### 5. **Search torrents (specific indexer)**

```bash
GET /api/v1/indexers/{indexer}/results?q={query}
```

**Parameters:**
- `q` (required): Search term
- `t` (optional): Search type
- `cat` (optional): Categories
- `limit` (optional): Result limit
- `offset` (optional): Offset

**Example:**
```bash
curl "http://localhost:15505/api/v1/indexers/dontorrent/results?q=avatar"
```

---

### 6. **Search TV series episodes (tvsearch)**

```bash
GET /api/v1/indexers/{indexer}/tvsearch?q={series}&season={season}&ep={episode}
```

**Parameters:**
- `q` (required): Series name
- `season` (optional): Season number
- `ep` (optional): Episode number
- `tvdbid` (optional): TVDB ID (Torznab)
- `rid` (optional): TVRage ID (Torznab)
- `imdbid` (optional): IMDB ID (Torznab)

**Behavior:**
- **Only `season`**: Returns ONLY complete season packs (empty array if no packs)
- **`season` + `ep`**: Returns ONLY individual episodes (empty array if not found)

**Examples:**

```bash
# Search for season 2 packs
curl "http://localhost:15505/api/v1/indexers/dontorrent/tvsearch?q=game%20of%20thrones&season=2"

# Search for specific episode
curl "http://localhost:15505/api/v1/indexers/dontorrent/tvsearch?q=game%20of%20thrones&season=2&ep=1"
```

**Response:**
```json
{
  "Results": [
    {
      "Title": "Game of Thrones S02E01 [HDTV-720p]",
      "Guid": "dontorrent-episode-12760",
      "Link": "http://localhost:15505/api/v1/indexers/dontorrent/download?url=...",
      "Details": "https://dontorrent.prof/serie/12759/12760/...",
      "Tracker": "DonTorrent",
      "Category": "Series",
      "Season": 2,
      "Episode": 1
    }
  ],
  "NumberOfResults": 1,
  "Query": "game of thrones",
  "Season": 2,
  "Episode": 1,
  "Indexer": "dontorrent"
}
```

**Title formatting:**
- Individual episode: `"Game of Thrones S02E01 [HDTV-720p]"`
- Complete pack: `"Game of Thrones - Season 2 Complete [HDTV-720p]"`

---

### 7. **Download torrent**

```bash
GET /api/v1/indexers/{indexer}/download?url={url}&tabla={tabla}&episode_id={id}
```

**Parameters:**
- `url` (required): Series/movie URL on DonTorrent
- `tabla` (required): Content type (`peliculas`, `series`, `documentales`)
- `content_id` (optional): Content ID for movies/documentaries
- `episode_id` (optional): Episode ID for series

**Example:**
```bash
LINK=$(curl -s "http://localhost:15505/api/v1/indexers/dontorrent/tvsearch?q=game%20of%20thrones&season=2&ep=1" | jq -r '.Results[0].Link')
curl -L "$LINK" -o episode.torrent
```

**Response:**
- `.torrent` file ready to use

---

## ⚙️ Configuration

Edit `config.yaml`:

```yaml
server:
  host: 0.0.0.0
  port: 15505
  debug: false

indexers:
  dontorrent:
    enabled: true
    domain: https://dontorrent.prof  # Change to current domain
    timeout: 30
```

---

## 🔧 Adding a new indexer

### 1. Create indexer class

`indexers/my_indexer.py`:

```python
from typing import List
from .base import BaseIndexer
from models import TorrentResult

class MyIndexer(BaseIndexer):
    @property
    def name(self) -> str:
        return "MyIndexer"
    
    def search(self, query: str) -> List[TorrentResult]:
        results = []
        # Implement your logic here
        return results
    
    def test_connection(self) -> bool:
        try:
            response = self.session.get(self.domain, timeout=10)
            return response.status_code == 200
        except:
            return False
```

### 2. Register in `indexers/__init__.py`

```python
from .my_indexer import MyIndexer

__all__ = ['BaseIndexer', 'DonTorrentIndexer', 'MyIndexer']
```

### 3. Add to mapping in `app.py`

```python
INDEXER_CLASSES = {
    'dontorrent': DonTorrentIndexer,
    'my_indexer': MyIndexer,
}
```

### 4. Configure in `config.yaml`

```yaml
indexers:
  my_indexer:
    enabled: true
    domain: https://my-indexer.com
    timeout: 30
```

---

## 📁 Project structure

```
indexarr/
├── app.py                    # Main Flask application
├── config.yaml               # Configuration
├── requirements.txt          # Python dependencies
├── Dockerfile                # Docker image (Alpine)
├── docker-compose.yml        # Compose for service deployment
├── Makefile                  # Management commands
├── README.md                 # Documentation
├── TVSEARCH.md              # Specific tvsearch documentation
├── indexers/                 # Indexers module
│   ├── __init__.py
│   ├── base.py              # Abstract base class
│   └── dontorrent.py        # DonTorrent implementation
├── models/                   # Data models
│   ├── __init__.py
│   └── torrent.py           # TorrentResult model
└── utils/                    # Utilities
    ├── __init__.py
    └── config_loader.py     # Configuration loader
```

---

## 🔒 DonTorrent notes

### Implemented features

1. **Proof of Work (PoW)**: Automatically solves SHA-256 cryptographic challenge
2. **Real search**: Uses DonTorrent's internal search system
3. **TVSearch**: Full support for series search with pack detection
4. **Session management**: Maintains appropriate cookies and headers
5. **Rate limiting**: Respects server limits

### Pack vs episode detection

The system automatically detects if a row is:

**Complete pack** (contains):
- Text: `" al "`, `" a "`, `"completa"`, `"todos"`, `"pack"`
- Ranges: `"1x01 al 1x10"`, `"01-10"`, `"1x01 1x10"`

**Individual episode**:
- Format: `"1x01 -"`, `"4x05 - Episode"`
- No pack indicators

### Known limitations

- PoW can take 3-10 seconds depending on difficulty
- Rate limiting of 60 downloads/hour implemented by server
- Some series may only have individual episodes (no packs)

---

## 📝 License

MIT

---

## 🐛 Troubleshooting

### Port already in use
```bash
# Change port in config.yaml
server:
  port: 15506  # Or any other free port
```

### Docker issues
```bash
make clean    # Clean everything
make rebuild  # Rebuild from scratch
```

### View logs
```bash
make logs     # Real-time logs
```

### DonTorrent not responding
- Verify domain in `config.yaml` is correct
- Run `make test` to test connection
