from app.extractor import get_video_info
import json

info = get_video_info('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
obj = {
    'title': info.get('title'),
    'best_format': info.get('best_format'),
    'count': len(info.get('formats') or []),
    'formats': (info.get('formats') or [])[:5],
}
with open('debug_extract_out.txt', 'w', encoding='utf-8') as f:
    json.dump(obj, f, ensure_ascii=False, indent=2)
print('done')
