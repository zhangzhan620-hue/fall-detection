# 基于vibecoding项目的全面存档——老人防摔智能识别

## 项目一句话简介

独居老人跌倒检测系统：电脑摄像头实时分析人体姿势，确认摔倒后本地报警并向手机 App 推送警报（响铃+现场截图+自动拨打家属电话），支持手机远程查看实时监控画面。

## 目录结构

```
项目存档_老人防摔智能识别/
├── 01_项目汇报/          课程论文（PDF 成品 + Markdown 源文件）
├── 02_源代码/
│   ├── PC端/             检测、报警、推送、训练等全部 Python 源码
│   └── 手机App端/        Android 报警接收端 App 源码（Kotlin）
├── 03_编译成品/          【体积过大未入库】Windows 成品与 APK 请从 Releases 下载
├── 04_模型与数据/        自训练模型权重 best.pt、姿势模型、训练数据集、数据配置
├── 05_论文素材/          论文全部插图（结构图、训练曲线、实测截图等）
└── 06_教学案例/          本项目转化的教学案例文档
```

## 快速运行

**电脑端（监控端）：**
```
03_编译成品\FallCamera\FallCamera.exe          # 摄像头模式
03_编译成品\FallCamera\FallCamera.exe 视频.mp4  # 视频测试模式
```

**手机端（接收端）：**
1. 安装 `03_编译成品\老人防摔App.apk`
2. 确认首页显示「推送通道: 已连接 ✓」
3. 把监控视频流地址改成电脑实际 IP（如 http://192.168.1.2:8080/video.mjpg）
4. 电池设为「不限制」、允许自启动

**二次开发（源码运行）：**
```powershell
python -m venv .venv && .\.venv\Scripts\pip install ultralytics opencv-python
.\.venv\Scripts\python.exe 02_源代码\PC端\pose_action_demo.py   # 注意: 需把 models 路径改回
```
