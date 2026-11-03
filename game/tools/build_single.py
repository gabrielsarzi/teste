#!/usr/bin/env python3
"""Gera um HTML único (JS embutido, three.js via CDN) para testar/compartilhar.

Uso: python3 tools/build_single.py saida.html [--artifact]
--artifact remove <html>/<head>/<body> para publicar como Artifact do Claude.
"""
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
out = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'dist' / 'ultimo-bunker.html'
artifact = '--artifact' in sys.argv

html = (root / 'index.html').read_text(encoding='utf-8')
html = html.replace('<script src="vendor/three.min.js"></script>',
                    '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>')

def inline(m):
    src = (root / m.group(1)).read_text(encoding='utf-8')
    return '<script>\n' + src.replace('</script>', '<\\/script>') + '\n</script>'

html = re.sub(r'<script src="(src/[^"]+)"></script>', inline, html)

if artifact:
    head = re.search(r'<head>(.*?)</head>', html, re.S).group(1)
    body = re.search(r'<body>(.*?)</body>', html, re.S).group(1)
    head = re.sub(r'<meta charset[^>]*>\s*', '', head)
    head = re.sub(r'<meta name="viewport"[^>]*>\s*', '', head)
    # o Artifact já aplica o recuo da área segura no :root
    head = head.replace('padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px);', '')
    html = head.strip() + '\n' + body.strip() + '\n'

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html, encoding='utf-8')
print('ok', out, len(html), 'bytes')
