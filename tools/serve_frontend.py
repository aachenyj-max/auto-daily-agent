#!/usr/bin/env python3
"""
serve_frontend.py

极简本地静态文件服务，用于在本机浏览器中查看前端页面。
使用方法：python tools/serve_frontend.py

工作目录设为项目根目录，因此：
  http://localhost:8080/frontend/   → 前端页面
  http://localhost:8080/output/      → 日报 Markdown 文件（只读）

按 Ctrl+C 停止服务。
"""

import http.server
import socketserver
import os
import sys

PORT = 8080
# 项目根目录（本文件在 tools/ 下，故上级目录为项目根）
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 静默访问日志，减少终端干扰


os.chdir(ROOT)
with socketserver.TCPServer(("", PORT), QuietHandler) as httpd:
    print(f"服务已启动：http://localhost:{PORT}/frontend/")
    print("按 Ctrl+C 停止服务")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
