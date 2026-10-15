# -*- coding: utf-8 -*-
"""论文 md -> html (修正图片路径) -> 供 Chrome 打印 PDF"""
import re

import markdown

SRC = r"论文\课程论文.md"
DST = "paper_build.html"

CSS = """
@page { margin: 2.2cm 2cm; }
body { font-family: "SimSun", "宋体", serif; font-size: 12pt; line-height: 1.8; color: #000; max-width: 750px; margin: 0 auto; }
h1 { font-family: "Microsoft YaHei", "黑体", sans-serif; font-size: 17pt; text-align: center; line-height: 1.5; }
h2 { font-family: "Microsoft YaHei", "黑体", sans-serif; font-size: 14pt; border-bottom: 1.5px solid #333; padding-bottom: 4px; margin-top: 28px; }
h3 { font-family: "Microsoft YaHei", "黑体", sans-serif; font-size: 12.5pt; margin-top: 20px; }
h4 { font-family: "Microsoft YaHei", "黑体", sans-serif; font-size: 12pt; margin-top: 16px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 10pt; }
th, td { border: 1px solid #555; padding: 5px 8px; text-align: center; }
th { background: #eee; }
code { font-family: Consolas, monospace; background: #f2f2f2; padding: 1px 4px; font-size: 10pt; }
pre { background: #f6f6f6; border: 1px solid #ddd; padding: 10px; font-size: 9.5pt; line-height: 1.5; white-space: pre-wrap; }
pre code { background: none; padding: 0; }
blockquote { border-left: 4px solid #999; margin-left: 0; padding: 2px 14px; color: #333; background: #f9f9f9; }
img { max-width: 100%; display: block; margin: 10px auto; }
hr { border: none; border-top: 1px solid #ccc; margin: 24px 0; }
"""

with open(SRC, encoding="utf-8") as f:
    text = f.read()

# 图片路径修正到项目根目录视角
text = re.sub(r"\]\((fig_[a-z_]+\.png)\)", r"](论文/素材/\1)", text)
text = text.replace("](my_model_demo.jpg)", "](论文/素材/my_model_demo.jpg)")

body = markdown.markdown(text, extensions=["tables", "fenced_code"])
html = f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{body}</body></html>'
with open(DST, "w", encoding="utf-8") as f:
    f.write(html)
print("html ok:", DST)
