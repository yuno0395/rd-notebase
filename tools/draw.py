"""Excalidraw図を組み立てる補助（開発担当者がExcalidrawで描く操作の代わり）"""
import json, re, secrets, hashlib
from kv import read_note, join_fm

def _id(): return secrets.token_hex(8)

class Drawing:
    def __init__(self): self.els = []; self.files = {}; self.n = 0
    def frame(self, name, x, y, w=800, h=566):   # A判比率 1:1.414
        self.n += 1; f = {'id': _id(), 'type': 'frame', 'x': x, 'y': y, 'width': w, 'height': h, 'name': name,
                          'customData': {'kvFrame': f'F{self.n:02d}'}}
        self.els.append(f); return f
    def _add(self, fr, d): d.update({'id': _id(), 'frameId': fr['id']}); self.els.append(d); return d
    def rect(self, fr, x, y, w, h, bg='transparent', sc='#1e1e1e'):
        return self._add(fr, {'type': 'rectangle', 'x': fr['x'] + x, 'y': fr['y'] + y, 'width': w, 'height': h, 'backgroundColor': bg, 'strokeColor': sc})
    def ellipse(self, fr, x, y, w, h, bg='transparent', sc='#1e1e1e'):
        return self._add(fr, {'type': 'ellipse', 'x': fr['x'] + x, 'y': fr['y'] + y, 'width': w, 'height': h, 'backgroundColor': bg, 'strokeColor': sc})
    def text(self, fr, x, y, t, fs=20, sc='#1e1e1e'):
        return self._add(fr, {'type': 'text', 'x': fr['x'] + x, 'y': fr['y'] + y, 'text': t, 'fontSize': fs, 'strokeColor': sc})
    def arrow(self, fr, x1, y1, x2, y2, sc='#1e1e1e', kind='arrow'):
        return self._add(fr, {'type': kind, 'x': fr['x'] + x1, 'y': fr['y'] + y1, 'points': [[0, 0], [x2 - x1, y2 - y1]], 'strokeColor': sc})
    def image(self, fr, x, y, w, h, filename):
        fid = hashlib.sha1(filename.encode()).hexdigest()[:16]; self.files[fid] = filename
        return self._add(fr, {'type': 'image', 'x': fr['x'] + x, 'y': fr['y'] + y, 'width': w, 'height': h, 'fileId': fid})
    def save(self, path):
        fm, body = read_note(path)
        from kv import text_part
        head = text_part(body); head = head + '\n%%\n# Excalidraw Data\n' if head else ''   # 図付きノートの文章は残す
        emb = '\n'.join(f'{k}: [[{v}]]' for k, v in self.files.items())
        texts = '\n\n'.join(e['text'] for e in self.els if e['type'] == 'text')
        body = head + (f"\n## Text Elements\n{texts}\n\n## Embedded Files\n{emb}\n\n## Drawing\n```json\n"
                + json.dumps({'type': 'excalidraw', 'elements': self.els, 'files': {}}, ensure_ascii=False, indent=1) + "\n```\n")
        if head: body = body.rstrip() + '\n%%\n'
        open(path, 'w', encoding='utf-8').write(join_fm(fm, body))

def load(path):
    """既存の図を読み込んで追記できるようにする"""
    from kv import parse_drawing, embedded_files
    fm, body = read_note(path); d = Drawing(); data = parse_drawing(body)
    d.els = data['elements']; d.files = embedded_files(body)
    d.n = len([e for e in d.els if e['type'] == 'frame'])
    return d
