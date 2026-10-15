# -*- coding: utf-8 -*-
"""训练自己的跌倒检测模型
基于 yolo26n 预训练权重微调, 数据集: fall/not-fallen 三分类(fall/standing/sitting)
训练完成后模型在 runs_fall/train_yolo26n/weights/best.pt
"""
from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO("yolo26n.pt")  # 首次运行自动下载预训练权重
    model.train(
        data="fall.yaml",
        epochs=30,        # CPU 训练先跑30轮, 效果不够可以再加
        imgsz=640,
        batch=8,
        workers=2,
        device="cpu",     # A卡Windows不支持CUDA, 先用CPU
        project="runs_fall",
        name="train_yolo26n",
    )
