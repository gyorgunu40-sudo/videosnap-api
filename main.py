from flask import Flask, request, jsonify, Response
import yt_dlp, os, tempfile, re

app = Flask(__name__)

ALLOWED_HOSTS = [
    'tiktok.com', 'vm.tiktok.com',
    'instagram.com', 'www.instagram.com',
    'youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com',
    'twitter.com', 'www.twitter.com', 'x.com', 'www.x.com',
]

FORMAT_MAP = {
    'mp4-720':  'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]',
    'mp4-1080': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]',
    'mp3':      'bestaudio/best',
}

API_KEY = os.environ.get('API_KEY', 'changeme')

def check_key():
    return request.headers.get('X-API-Key') == API_KEY

def validate_url(url):
    from urllib.parse import urlparse
    try:
        h = urlparse(url).netloc.lower().lstrip('www.')
        return any(h == a or h.endswith('.' + a) for a in ALLOWED_HOSTS)
    except:
        return False

@app.route('/info', methods=['POST'])
def info():
    if not check_key():
        return jsonify({'error': 'Yetkisiz'}), 401
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    if not url or not validate_url(url):
        return jsonify({'error': 'Geçersiz URL'}), 400

    ydl_opts = {
        'quiet': True, 'no_warnings': True,
        'socket_timeout': 15, 'noplaylist': True,
        'extractor_args': {'youtube': {'player_client': ['ios', 'web']}},
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return jsonify({'error': 'Video bilgisi alınamadı: ' + str(e)}), 500

    heights = [f.get('height') for f in info.get('formats', []) if f.get('height')]
    formats = []
    max_h = max(heights) if heights else 0
    if not heights or max_h >= 720:
        formats.append({'code': 'mp4-720', 'label': 'MP4 — 720p HD'})
    if max_h >= 1080:
        formats.append({'code': 'mp4-1080', 'label': 'MP4 — 1080p Full HD'})
    formats.append({'code': 'mp3', 'label': 'MP3 — Sadece Ses'})

    return jsonify({
        'title':     info.get('title', 'Video')[:200],
        'thumbnail': info.get('thumbnail'),
        'duration':  info.get('duration'),
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
    if fmt not in FORMAT_MAP:
        return jsonify({'error': 'Geçersiz format'}), 400

    is_audio = fmt == 'mp3'
    ext = 'mp3' if is_audio else 'mp4'
    tmp = tempfile.mktemp(suffix='.' + ext)

    ydl_opts = {
        'quiet': True, 'no_warnings': True,
        'socket_timeout': 30, 'noplaylist': True,
        'format': FORMAT_MAP[fmt],
        'outtmpl': tmp,
        'merge_output_format': ext,
        'extractor_args': {'youtube': {'player_client': ['ios', 'web']}},
    }
    if is_audio:
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '0',
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        return jsonify({'error': 'İndirme başarısız: ' + str(e)}), 500

    # Gerçek dosyayı bul
    actual = tmp
    if not os.path.exists(actual):
        import glob
        files = glob.glob(tmp.replace('.' + ext, '') + '*')
        actual = files[0] if files else None

    if not actual or not os.path.exists(actual):
        return jsonify({'error': 'Dosya oluşturulamadı'}), 500

    mime = 'audio/mpeg' if is_audio else 'video/mp4'
    filename = f'videosnap.{ext}'

    def generate():
        with open(actual, 'rb') as f:
            while chunk := f.read(8192):
                yield chunk
        os.unlink(actual)

    return Response(
        generate(),
        mimetype=mime,
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(os.path.getsize(actual)),
        }
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
