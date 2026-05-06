# Web → Telegraph

一键抓取网页正文，自动发布到 [Telegraph](https://telegra.ph/)。

## 快速开始

```bash
# 1. 安装依赖
pip install readability-lxml html-telegraph-poster trafilatura requests

# 2. 启动交互菜单（推荐！）
python web2telegraph.py
```

## 功能

| 特性 | 说明 |
|------|------|
| 🧠 智能提取 | readability-lxml → trafilatura 三级回退 |
| 🖼️ 图片上传 | 自动将页面图片上传到 Telegraph 图床 |
| 📋 批量抓取 | 一次粘贴多个 URL，逐个处理 |
| ✏️ 标题自定义 | 发布前可修改标题和作者 |
| 💾 Token 持久化 | 配置一次，永久使用 |

## 交互菜单

启动后看到的就是这样，跟着提示选就行：

```
==================================================
   📰 Web → Telegraph 网页转存工具
==================================================
   Token: ✅ 已配置  |  作者: 你的名字
--------------------------------------------------
   1. 抓取网页并发布到 Telegraph
   2. 配置/重新配置 Telegraph 账号
   3. 查看已有配置
   0. 退出
--------------------------------------------------
👉 请选择 [1]:
```

## CLI 快速模式（也支持）

```bash
python web2telegraph.py https://example.com/article
python web2telegraph.py URL -t "标题" -a "作者"
python web2telegraph.py URL --no-images
python web2telegraph.py URL1 URL2 URL3   # 批量
```

## 原理

```
网页 URL
   │
   ▼
┌─────────────────┐
│  readability-lxml │ ◄── 首选：Mozilla Readability 算法
│  (提取失败?)      │
│  trafilatura      │ ◄── 回退1：更激进的正文识别
│  (提取失败?)      │
│  readability 兜底 │ ◄── 回退2：强制提取
└─────────────────┘
   │ 正文 HTML
   ▼
┌─────────────────┐
│ 图片 → Telegraph │ ◄── 自动上传外部图片到 Telegraph 图床
│ 图床             │
└─────────────────┘
   │
   ▼
┌─────────────────┐
│ Telegraph API    │ ◄── 发布页面
│ telegra.ph/xxx   │
└─────────────────┘
```
