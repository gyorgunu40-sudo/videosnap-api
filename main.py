from flask import Flask, request, jsonify, Response
import os, requests
from urllib.parse import urlparse

app = Flask(__name__)

ALLOWED_HOSTS = [
    'tiktok.com', 'vm.tiktok.com',
    'instagram.com', 'www.instagram.com',
    'youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com',
    'twitter.com', 'www.twitter.com', 'x.com', 'www.x.com',
]

API_KEY = os.environ.get('API_KEY', 'changeme')
COBALT_API = 'https://api.cobalt.tools'

def check_key():
    return request.headers.get('X-API-Key') == API_KEY

def validate_url(url):
    try:
        h = urlparse(url).netloc.lower()
        if h.startswith('www.'): h = h[4:]
        return any(h == a or h.endswith('.' + a) for a in ALLOWED_HOSTS)
    except:
        return False

def detect_platform(url):
    host = urlparse(url).netloc.lower()
    if 'youtube' in host or 'youtu.be' in host: return 'youtube'
    if 'tiktok' in host: return 'tiktok'
    if 'instagram' in host: return 'instagram'
    return 'twitter'

def cobalt_request(url, fmt):
    is_audio = fmt == 'mp3'
    payload = {
        'url': url,
        'videoQuality': '1080' if fmt == 'mp4-1080' else '720',
        'audioFormat': 'mp3',
        'downloadMode': 'audio' if is_audio else 'auto',
        'filenameStyle': 'basic',
    }
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0',
    }
    try:
        r = requests.post(COBALT_API, json=payload, headers=headers, timeout=30)
        return r.json()
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

@app.route('/info', methods=['POST'])
def info():
    if not check_key():
        return jsonify({'error': 'Yetkisiz'}), 401
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    if not url or not validate_url(url):
        return jsonify({'error': 'Geçersiz URL'}), 400

    result = cobalt_request(url, 'mp4-720')
    status = result.get('status', '')

    if status == 'error':
        return jsonify({'error': 'Video bulunamadı: ' + str(result.get('error', ''))}), 500

    platform = detect_platform(url)
    formats = [
        {'code': 'mp4-720',  'label': 'MP4 — 720p HD'},
        {'code': 'mp4-1080', 'label': 'MP4 — 1080p Full HD'},
        {'code': 'mp3',      'label': 'MP3 — Sadece Ses'},
    ]

    title = result.get('filename', 'Video')
    title = title.rsplit('.', 1)[0].replace('-', ' ').replace('_', ' ')

    return jsonify({
        'title':    title[:200],
        'thumbnail': None,
        'duration':  None,
        'platform':  platform,
        'formats':   formats,
    })

@app.route('/download', methods=['GET'])
def download():
    if not check_key():
        return jsonify({'error': 'Yetkisiz'}), 401
    url = request.args.get('url', '').strip()
    fmt = request.args.get('format', 'mp4-720')
    if not url or not validate_url(url):
        return jsonify({'error': 'Geçersiz URL'}), 400
    if fmt not in ('mp4-720', 'mp4-1080', 'mp3'):
        return jsonify({'error': 'Geçersiz format'}), 400

    result = cobalt_request(url, fmt)
    status = result.get('status', '')

    if status == 'error':
        return jsonify({'error': 'İndirme başarısız: ' + str(result.get('error', ''))}), 500

    # tunnel = Cobalt direkt stream ediyor
    # redirect = Cobalt başka URL'ye yönlendiriyor
    # stream = Cobalt stream URL veriyor
    download_url = result.get('url')
    if not download_url:
        return jsonify({'error': 'İndirme linki alınamadı. Cobalt yanıtı: ' + str(result)}), 500

    is_audio = fmt == 'mp3'
    ext = 'mp3' if is_audio else 'mp4'
    mime = 'audio/mpeg' if is_audio else 'video/mp4'
    filename = f'videosnap.{ext}'

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(download_url, stream=True, timeout=120, headers=headers)
        def generate():
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        return Response(
            generate(),
            mimetype=mime,
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        return jsonify({'error': 'Dosya aktarım hatası: ' + str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
