# -*- coding: utf-8 -*-
"""Markdown -> 带中文样式的 HTML"""
import sys

import markdown

src, dst = sys.argv[1], sys.argv[2]

CSS = """
@page { margin: 2.2cm 2cm; }
body { font-family: "SimSun", "宋体", serif; font-size: 12pt; line-height: 1.8; color: #000; max-width: 750px; margin: 0 auto; }
h1 { font-family: "Microsoft YaHei", "黑体", sans-serif; font-size: 18pt; text-align: center; line-height: 1.5; }
h2 { font-family: "Microsoft YaHei", "黑体", sans-serif; font-size: 14pt; border-bottom: 1.5px solid #333; padding-bottom: 4px; margin-top: 28px; }
h3 { font-family: "Microsoft YaHei", "黑体", sans-serif; font-size: 12.5pt; margin-top: 20px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 10.5pt; }
th, td { border: 1px solid #555; padding: 5px 8px; text-align: center; }
th { background: #eee; }
code { font-family: Consolas, monospace; background: #f2f2f2; padding: 1px 4px; font-size: 10pt; }
pre { background: #f6f6f6; border: 1px solid #ddd; padding: 10px; font-size: 9.5pt; line-height: 1.5; white-space: pre-wrap; }
pre code { background: none; padding: 0; }
blockquote { border-left: 4px solid #999; margin-left: 0; padding: 2px 14px; color: #333; background: #f9f9f9; }
strong { font-weight: bold; }
hr { border: none; border-top: 1px solid #ccc; margin: 24px 0; }
img { max-width: 100%; display: block; margin: 14px auto; border: 1px solid #ddd; }
"""

with open(src, encoding="utf-8") as f:
    text = f.read()

body = markdown.markdown(text, extensions=["tables", "fenced_code"])
html = f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{body}</body></html>'

with open(dst, "w", encoding="utf-8") as f:
    f.write(html)
print("html ok:", dst)
