#!/usr/bin/env python3
"""Локальный сервер для ArtSpace: python3 serve.py [порт]
Тема, избранное и уведомление запоминаются надёжнее, чем при открытии файлов через file://."""
import http.server, os, sys, threading, webbrowser

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
url = f'http://127.0.0.1:{PORT}/index.html'
print('ArtSpace:', url, '(Ctrl+C — остановить)')
threading.Timer(0.6, lambda: webbrowser.open(url)).start()
try:
    srv.serve_forever()
except KeyboardInterrupt:
    print('\nОстановлено')