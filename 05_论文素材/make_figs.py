# -*- coding: utf-8 -*-
"""生成课程论文用图：YOLO26n 结构图 / 微调原理图 / 姿势估计原理图"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mp
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.image as mpimg

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

# ---------- 通用配色 ----------
C_INPUT  = "#E8EEF7"  # 浅蓝灰
C_BACK   = "#DCE9F9"  # 主干-蓝
C_NECK   = "#E2F0E3"  # 颈部-绿
C_HEAD   = "#FDEBD3"  # 检测头-橙
C_OUT    = "#F6E3EA"  # 输出-粉
C_EDGE   = "#5B6B7C"
C_PRE    = "#4A7EBB"  # 预训练蓝
C_NEW    = "#D9822B"  # 微调橙
TXT      = "#22303F"

def box(ax, x, y, w, h, label, fc, fs=11, ec=C_EDGE, bold=True, sub=None, subfs=9, lw=1.2, r=0.06):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=2))
    if sub:
        ax.text(x + w/2, y + h*0.62, label, ha="center", va="center", fontsize=fs,
                fontweight="bold" if bold else "normal", color=TXT, zorder=3)
        ax.text(x + w/2, y + h*0.30, sub, ha="center", va="center", fontsize=subfs, color="#5A6B7D", zorder=3)
    else:
        ax.text(x + w/2, y + h/2, label, ha="center", va="center", fontsize=fs,
                fontweight="bold" if bold else "normal", color=TXT, zorder=3)

def arrow(ax, x1, y1, x2, y2, color=C_EDGE, lw=1.8, style="-|>", ls="-", ms=14):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=ms,
                                 color=color, lw=lw, linestyle=ls, zorder=4,
                                 shrinkA=1, shrinkB=1))

def grouplabel(ax, x, y, text, color, fs=13):
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, fontweight="bold", color=color, zorder=3)

# ======================================================================
# 图 A：YOLO26n 网络结构图
# ======================================================================
fig, ax = plt.subplots(figsize=(16.5, 8.2), dpi=200)
ax.set_xlim(0, 16.5); ax.set_ylim(0, 8.2); ax.axis("off")

# ---- 输入 ----
box(ax, 0.15, 3.4, 1.15, 1.5, "输入图像", C_INPUT, sub="3 × 640 × 640")

# ---- Backbone ----
bx, bw = 1.75, 4.0
ax.add_patch(FancyBboxPatch((bx-0.15, 1.45), bw+0.3, 5.6, boxstyle="round,pad=0,rounding_size=0.12",
             fc="#F4F8FD", ec=C_PRE, lw=1.6, zorder=1))
grouplabel(ax, bx + bw/2, 6.72, "Backbone 主干网络（特征提取）", C_PRE)
stages = [
    ("Stem：Conv 3×3/s2 ×2",      "640 → 160，16/32 ch"),
    ("C3k2 Stage2",                "160×160，64 ch"),
    ("C3k2 Stage3",                "80×80，128 ch"),
    ("C3k2 Stage4",                "40×40，128 ch"),
    ("C3k2 + SPPF + C2PSA",        "20×20，256 ch，注意力增强"),
]
for i, (name, sub) in enumerate(stages):
    y = 5.45 - i * 0.92
    box(ax, bx, y, bw, 0.72, name, C_BACK, sub=sub, fs=11.5, subfs=9.5)
    if i:
        arrow(ax, bx + bw/2, y + 0.92 + 0.02, bx + bw/2, y + 0.72, lw=1.6)

# ---- Neck ----
nx, nw = 6.55, 3.1
ax.add_patch(FancyBboxPatch((nx-0.15, 1.45), nw+0.3, 5.6, boxstyle="round,pad=0,rounding_size=0.12",
             fc="#F3FAF4", ec="#3E8E5A", lw=1.6, zorder=1))
grouplabel(ax, nx + nw/2, 6.72, "Neck 颈部（PAN-FPN 多尺度融合）", "#3E8E5A")
# 融合节点 P3 P4 P5
box(ax, nx + 0.55, 4.95, 2.0, 0.72, "P3 融合特征", C_NECK, sub="80×80×64  小目标", fs=11)
box(ax, nx + 0.55, 3.55, 2.0, 0.72, "P4 融合特征", C_NECK, sub="40×40×128  中目标", fs=11)
box(ax, nx + 0.55, 2.15, 2.0, 0.72, "P5 融合特征", C_NECK, sub="20×20×256  大目标", fs=11)
ax.text(nx + nw/2, 1.72, "自顶向下上采样 ⊕ 自底向上采样\n深浅层特征拼接（Concat）", ha="center", va="center",
        fontsize=9.5, color="#5A6B7D", zorder=3)
# backbone -> neck 箭头（三条支路 + 主路）
bb_right = bx + bw
arrow(ax, bb_right + 0.15, 2.15 + 0.36, nx - 0.15, 2.15 + 0.36, lw=1.6)                       # stage5 -> P5
arrow(ax, bb_right + 0.15, 3.53 + 0.36, nx + 0.4, 3.55 + 0.72, lw=1.3, style="-|>", ls=(0,(4,2))) # stage4 -/ P4
arrow(ax, bb_right + 0.15, 4.45 + 0.36, nx + 0.4, 4.95 + 0.72, lw=1.3, ls=(0,(4,2)))          # stage3 -/ P3
ax.text(6.15, 5.6, "跨层连接", fontsize=8.5, color="#7A8794", ha="center", rotation=18)
# P5 -> P4 -> P3 上采样，P3 -> P4 -> P5 下采样
arrow(ax, nx + 1.05, 2.87, nx + 1.05, 3.55, lw=1.3)
arrow(ax, nx + 1.05, 4.27, nx + 1.05, 4.95, lw=1.3)
arrow(ax, nx + 2.05, 4.95, nx + 2.05, 4.27, lw=1.3, ls=(0,(4,2)))
arrow(ax, nx + 2.05, 3.55, nx + 2.05, 2.87, lw=1.3, ls=(0,(4,2)))

# ---- Head ----
hx, hw = 10.25, 4.05
ax.add_patch(FancyBboxPatch((hx-0.15, 1.45), hw+0.3, 5.6, boxstyle="round,pad=0,rounding_size=0.12",
             fc="#FDF8F0", ec=C_NEW, lw=1.6, zorder=1))
grouplabel(ax, hx + hw/2, 6.72, "Head 检测头（解耦头 × 3 尺度）", C_NEW)
for i, p in enumerate(["P3", "P4", "P5"]):
    y = 5.05 - i * 1.55
    box(ax, hx, y, 1.85, 0.95, f"{p} 回归分支", C_HEAD, sub="Conv×2\n框 (x,y,w,h)", fs=10.5, subfs=8.5)
    box(ax, hx + 2.2, y, 1.85, 0.95, f"{p} 分类分支", C_HEAD, sub="DWConv×2\n类别置信度", fs=10.5, subfs=8.5)
# neck -> head
arrow(ax, nx + nw + 0.15, 5.31, hx - 0.15, 5.31, lw=1.6)
arrow(ax, nx + nw + 0.15, 3.91, hx - 0.15, 3.91, lw=1.6)
arrow(ax, nx + nw + 0.15, 2.51, hx - 0.15, 2.51, lw=1.6)

# ---- 输出 ----
box(ax, 14.75, 3.35, 1.65, 1.6, "检测结果", C_OUT, fs=12,
    sub="检测框+类别\n+置信度\n（免 NMS）", subfs=9)
arrow(ax, hx + hw + 0.15, 4.15, 14.75, 4.15, lw=1.8)

# ---- 底部图例 ----
legend = ("模块说明：Conv = 卷积 + BN + SiLU　|　C3k2 = 跨阶段部分连接的瓶颈模块（梯度分流、轻量高效）　|　"
          "SPPF = 空间金字塔快速池化（扩大感受野）\nC2PSA = 位置敏感注意力模块（聚焦关键区域）　|　"
          "DWConv = 深度可分离卷积（降低计算量）　|　n = nano 最轻量规格，检测模型约 2.6M 参数 / 5.4MB")
ax.text(8.25, 0.62, legend, ha="center", va="center", fontsize=9.5, color="#42505F",
        bbox=dict(boxstyle="round,pad=0.5", fc="#F6F8FA", ec="#C9D3DD", lw=1))

fig.savefig("fig_yolo_arch.png", bbox_inches="tight", facecolor="white")
plt.close(fig)
print("fig_yolo_arch.png OK")

# ======================================================================
# 图 B：微调（迁移学习）原理图 —— 专业版
# ======================================================================
fig, ax = plt.subplots(figsize=(15, 8.6), dpi=200)
ax.set_xlim(0, 15); ax.set_ylim(0, 8.6); ax.axis("off")

def netblock(ax, x, y, w=1.9, h=1.1, label="", sub="", fc=C_BACK, ec=C_EDGE):
    box(ax, x, y, w, h, label, fc, sub=sub, fs=11, subfs=8.5, ec=ec)

# ---------- 上半：预训练 ----------
grouplabel(ax, 1.5, 7.9, "① 预训练阶段（Ultralytics 官方完成，公开权重）", C_PRE, fs=13)
box(ax, 0.35, 6.35, 2.3, 1.15, "COCO 数据集", C_INPUT, sub="≈11.8 万张标注图 / 80 类", fs=11.5)
netblock(ax, 3.4, 6.35, label="Backbone 主干", sub="通用视觉特征", fc=C_BACK)
netblock(ax, 5.65, 6.35, label="Neck 颈部", sub="多尺度融合", fc=C_NECK)
netblock(ax, 7.9, 6.35, label="Head 检测头", sub="分类分支 = 80 类", fc=C_HEAD)
box(ax, 10.55, 6.35, 2.3, 1.15, "预训练权重", "#E3ECF8", sub="yolo26n.pt（会认 80 类）", fs=11.5, ec=C_PRE)
for x1, x2 in [(2.65, 3.4), (5.3, 5.65), (7.55, 7.9), (9.8, 10.55)]:
    arrow(ax, x1, 6.93, x2, 6.93, lw=1.8)
ax.text(13.05, 6.93, "成本：大规模 GPU 集群\n数千 GPU·小时", fontsize=9.5, color="#7A8794", va="center")

# ---------- 权重迁移 ----------
arrow(ax, 11.7, 6.35, 11.7, 4.6, color=C_PRE, lw=2.2, ls=(0, (5, 3)))
ax.text(11.85, 5.45, "权重迁移\n（直接加载，不重学）", fontsize=10.5, color=C_PRE, va="center", fontweight="bold")

# ---------- 下半：微调 ----------
grouplabel(ax, 1.5, 4.15, "② 微调阶段（本项目完成，纯 CPU 48 分钟）", C_NEW, fs=13)
box(ax, 0.35, 2.9, 2.3, 1.15, "跌倒数据集", C_INPUT, sub="374 张标注图 / 3 类", fs=11.5)
# 继承部分：加“继承”标记
netblock(ax, 3.4, 2.9, label="Backbone 主干", sub="★ 继承通用视觉特征", fc=C_BACK, ec=C_PRE)
netblock(ax, 5.65, 2.9, label="Neck 颈部", sub="★ 继承多尺度融合", fc=C_NECK, ec=C_PRE)
netblock(ax, 7.9, 2.9, label="Head 检测头", sub="◆ 分类分支 80→3 类", fc="#FBE3C2", ec=C_NEW)
box(ax, 10.55, 2.9, 2.3, 1.15, "微调后模型", "#FDEBD3", sub="best.pt（会认 fall 等 3 类）", fs=11.5, ec=C_NEW)
for x1, x2 in [(2.65, 3.4), (5.3, 5.65), (7.55, 7.9), (9.8, 10.55)]:
    arrow(ax, x1, 3.48, x2, 3.48, lw=1.8)

# 反向传播
arrow(ax, 10.4, 2.62, 3.55, 2.62, color="#C0392B", lw=1.8, ls=(0, (5, 3)))
ax.text(6.9, 2.38, r"损失反向传播：全部层以小学习率继续更新（0.01 → $6\times10^{-5}$）", fontsize=9.5,
        color="#C0392B", ha="center", va="center")

# 对比框
ax.text(7.5, 1.35,
        "★ 继承的部分：预训练学到的“看图基本功”（边缘、纹理、轮廓、人体结构）——374 张小数据集学不出来，直接复用\n"
        "◆ 改造的部分：只有检测头最后一层分类卷积（输出通道 80 → 3）因类别数变化而重建，其余权重全部作为起点\n"
        "结果：从头训练需要数万张图 + GPU 数天 → 微调只需 374 张图 + CPU 48 分钟，fall 类 mAP@50 达 0.97",
        ha="center", va="center", fontsize=10, color="#42505F",
        bbox=dict(boxstyle="round,pad=0.6", fc="#F6F8FA", ec="#C9D3DD", lw=1))

fig.savefig("fig_finetune.png", bbox_inches="tight", facecolor="white")
plt.close(fig)
print("fig_finetune.png OK")

# ======================================================================
# 图 C：姿势估计（关键点识别）原理图
# ======================================================================
fig = plt.figure(figsize=(15.5, 6.8), dpi=200)
gs = fig.add_gridspec(1, 2, width_ratios=[1.05, 1.0], wspace=0.02)

# ---- 左：流程 ----
ax = fig.add_subplot(gs[0]); ax.set_xlim(0, 8); ax.set_ylim(0, 6.8); ax.axis("off")
grouplabel(ax, 4.0, 6.45, "Top-Down 姿势估计：先检测人，再回归关键点", TXT, fs=12.5)
box(ax, 0.2, 3.1, 1.5, 1.2, "输入图像", C_INPUT, sub="3 × 640 × 640")
box(ax, 2.15, 3.1, 1.9, 1.2, "共享主干+颈部", C_BACK, sub="（与检测模型相同）", fs=11)
# 两个分支
box(ax, 4.6, 4.35, 1.75, 1.15, "检测分支", C_HEAD, sub="人体框 + 置信度\n（先找到“人在哪”）", fs=11, subfs=8.5)
box(ax, 4.6, 1.85, 1.75, 1.15, "关键点分支 cv4", C_HEAD, sub="回归 17 × (x, y, σ)\nσ = 该点置信度", fs=11, subfs=8.5)
box(ax, 6.7, 3.1, 1.15, 1.2, "骨架\n输出", C_OUT, fs=11, sub="框 + 17 点", subfs=8.5)
arrow(ax, 1.7, 3.7, 2.15, 3.7, lw=1.8)
arrow(ax, 4.05, 3.85, 4.6, 4.7, lw=1.8)
arrow(ax, 4.05, 3.55, 4.6, 2.7, lw=1.8)
arrow(ax, 6.35, 4.9, 6.75, 4.25, lw=1.8)
arrow(ax, 6.35, 2.45, 6.75, 3.15, lw=1.8)
ax.text(4.0, 1.15, "每个检测框独立预测 17 个关节点坐标——关键点之间相互独立回归，\n"
                   "不存在“连线搜索”，因此速度快且天然支持多人", ha="center", va="center",
        fontsize=9.5, color="#5A6B7D")

# ---- 右：真实推理结果 ----
ax2 = fig.add_subplot(gs[1]); ax2.axis("off")
img = mpimg.imread("fig_src/v2_180s_crop.jpg")
ax2.imshow(img)
ax2.set_title("YOLO26n-pose 实测输出（17 关键点 + 骨架连线）", fontsize=12.5,
              fontweight="bold", color=TXT, pad=6)
fig.savefig("fig_pose_head.png", bbox_inches="tight", facecolor="white")
plt.close(fig)
print("fig_pose_head.png OK")
