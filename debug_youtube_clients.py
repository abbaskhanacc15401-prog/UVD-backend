import yt_dlp

urls = [
    'https://www.youtube.com/watch?v=jNQXAC9IVRw',
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'https://www.youtube.com/watch?v=ysz5S6PUM-U',
    'https://www.youtube.com/watch?v=aqz-KE-bpKQ',
]
clients = ['default', 'web', 'ios', 'android', 'tv_embedded', 'mweb', 'tv']

for url in urls:
    print('URL:', url)
    for client in clients:
        opts = {
            'skip_download': True,
            'quiet': True,
            'noplaylist': True,
            'extractor_args': {'youtube': [f'player_client={client}']},
            'ignoreerrors': True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if isinstance(info, dict):
                print('  OK client=', client, 'title=', info.get('title'))
                break
        except Exception as e:
            print('  ERR client=', client, type(e).__name__, str(e)[:180])
    else:
        print('  FAILED ALL CLIENTS')
