# Video Downloader - 视频下载工具完整开发文档

## 📖 目录

- [项目概述](#项目概述)
- [功能特性](#功能特性)
- [技术架构](#技术架构)
- [开发历程](#开发历程)
- [安装与使用](#安装与使用)
- [常见问题](#常见问题)
- [API 参考](#api-参考)
- [打包发布](#打包发布)

---

## 项目概述

Video Downloader 是一个功能强大的视频下载工具，支持多种视频格式和流媒体协议。项目经历了从命令行工具到图形界面的完整开发过程，最终实现了一个用户友好、功能全面的下载解决方案。

### 核心能力

- **多协议支持**：HLS/M3U8、DASH/MPD、RTMP、HTTP/HTTPS 直链
- **多格式支持**：MP4、MKV、AVI、MOV、WEBM、FLV、TS
- **网站解析**：YouTube、Bilibili、优酷、腾讯视频、爱奇艺等
- **P2P 下载**：磁力链接、BT 种子
- **直播录制**：支持直播流实时录制

---

## 功能特性

### 🚀 下载引擎

| 引擎 | 适用类型 | 特点 |
|------|----------|------|
| **DirectHlsEngine** | M3U8/HLS | 基于 N_m3u8DL-RE，支持加密、多线程 |
| **DirectDownloadEngine** | 直链视频 | 内置 HTTP 下载器，支持多线程分块 |
| **DashEngine** | DASH/MPD | 基于 yt-dlp，支持自适应码率 |
| **WebsiteEngine** | YouTube/Bilibili等 | 基于 yt-dlp，支持上千个网站 |
| **P2pEngine** | 磁力/BT | 基于 aria2，支持 DHT 网络 |
| **LiveEngine** | 直播流 | 基于 FFmpeg，支持实时录制 |

### 🎨 图形界面

- **下载标签页**：URL 输入、请求头配置、进度显示
- **历史记录标签页**：下载历史、搜索、打开文件
- **日志标签页**：实时日志输出、调试信息
- **深色主题**：舒适的视觉体验

### ⚙️ 高级功能

- **自定义请求头**：支持 Referer、User-Agent、Cookie、Authorization
- **Cookie 导入**：从 Chrome/Firefox/Edge 导入
- **多线程下载**：可配置线程数（1-32）
- **断点续传**：中断后可继续下载
- **批量下载**：支持从文件导入 URL 列表
- **格式转换**：输出 MP4/MKV/原格式
- **画质选择**：best/1080p/720p/480p/360p/worst

---

## 技术架构

### 技术栈
┌─────────────────────────────────────────────────────────────┐
│ 图形界面 (PyQt6) │
├─────────────────────────────────────────────────────────────┤
│ 下载调度器 (Scheduler) │
├─────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│ │ Direct │ │ HLS │ │ DASH │ │ Website │ │
│ │ Engine │ │ Engine │ │ Engine │ │ Engine │ │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│ │ P2P │ │ Live │ │ FFmpeg │ │
│ │ Engine │ │ Engine │ │ Helper │ │
│ └──────────┘ └──────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────────┤
│ 第三方工具集成 │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│ │ N_m3u8DL-RE │ │ yt-dlp │ │ aria2c │ │
│ │ (HLS下载) │ │ (网站解析) │ │ (P2P下载) │ │
│ └──────────────┘ └──────────────┘ └──────────────┘ │
└─────────────────────────────────────────────────────────────┘


### 核心模块

#### 1. 请求头管理 (`headers/`)
- `HeaderManager`：请求头创建、合并、验证
- `UserAgentPresets`：常用浏览器 UA 预设
- `CookieImporter`：浏览器 Cookie 导入

#### 2. 数据模型 (`models/`)
- `DownloadOptions`：下载配置
- `DownloadResult`：下载结果
- `RequestHeaders`：HTTP 请求头
- `VideoInfo`：视频信息

#### 3. 工具类 (`utils/`)
- `LinkDetector`：链接类型识别
- `FFmpegHelper`：格式转换
- `ProgressDisplay`：进度显示
- `ConfigManager`：配置管理

---

## 开发历程

### 第一阶段：命令行工具

从基础开始，实现了：

```python```
# 基础下载引擎
```
class BaseEngine(ABC):
    @abstractmethod
    async def download(...): pass
```
#### 关键突破：

实现 HLS 下载（N_m3u8DL-RE 集成）
实现直链下载（aiohttp）
链接类型识别

### 第二阶段：图形界面
使用 PyQt6 构建 GUI：
```
# 主窗口结构
class MainWindow(QMainWindow):
    def __init__(self):
        self.download_tab = DownloadTab()
        self.history_tab = HistoryTab()
        self.settings_tab = SettingsTab()
```
关键突破：

QThread 异步下载

信号/槽通信

深色主题

### 第三阶段：调试与优化
遇到的典型问题及解决方案：

#### 403 Forbidden

原因：缺少 Referer/User-Agent

解决：添加请求头配置

#### N_m3u8DL-RE 参数错误

原因：--skip-existing 参数不支持

解决：移除不支持的参数

#### 请求头引号问题

原因：User-Agent 包含空格未被引号包裹

解决：-H "User-Agent: Mozilla/5.0..."

#### 多线程下载卡住

原因：共享 aiohttp session 导致阻塞

解决：每个分块独立 session

#### 任务重复执行

原因：任务队列未清空

解决：每次下载创建新 worker

### 第四阶段：打包发布
使用 PyInstaller 打包为独立可执行文件
```
pyinstaller --onefile --windowed --add-data "src;src" --add-data "config;config" run_simple_gui.py
```

## 安装与使用
### 环境要求
Python 3.9+（源码运行）
Windows 10/11（推荐，支持 macOS/Linux）
.NET Framework 4.8+（N_m3u8DL-RE 需要）
FFmpeg（可选，格式转换需要）

### 从源码运行
```
# 克隆仓库
git clone https://github.com/yourname/video-downloader.git
cd video-downloader

# 安装依赖
pip install -r requirements.txt

# 运行
python run_simple_gui.py
```

### 使用可执行文件
下载 VideoDownloader_Portable.zip

解压到任意目录

双击 VideoDownloader.exe

### 基本使用流程
```
1. 输入视频链接
   ↓
2. 配置请求头（Referer、User-Agent、Cookie）
   ↓
3. 选择保存目录
   ↓
4. 设置线程数、输出格式
   ↓
5. 点击"开始下载"
   ↓
6. 等待下载完成
```
#### 请求头配置示例
```
# 基础配置
Referer: https://example.com
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36

# 需要登录
Cookie: session_id=abc123; user_token=xyz789

# API 认证
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

# 自定义头
X-Custom-Header: custom_value
```

常见问题
Q1: 下载失败，返回 403 Forbidden
原因：服务器拒绝访问，通常缺少必要的请求头。

解决方案：

添加正确的 Referer（视频所在页面 URL）

添加 User-Agent 模拟浏览器

如需登录，添加 Cookie

Q2: 如何获取正确的 Referer？
Referer 是视频所在网页的完整 URL，不是 M3U8 文件本身的 URL。
错误: https://cdn.example.com/video.m3u8
正确: https://example.com/watch/123
获取方法：

在浏览器打开视频页面

按 F12 打开开发者工具

在 Network 标签找到 .m3u8 请求

查看 Request Headers 中的 Referer

Q3: Cookie 导入失败
原因：浏览器正在运行，Cookie 文件被锁定。

解决方案：

关闭浏览器后重试

手动复制 Cookie：

安装 Cookie-Editor 扩展

导出 Cookie

粘贴到请求头区域

Q4: 下载速度慢
优化建议：

增加线程数（8-16）

检查网络连接

服务器可能限速（换时间段下载）

使用代理/VPN

Q5: 进度条不动但程序在运行
原因：进度解析正则表达式不匹配 N_m3u8DL-RE 输出格式。

解决方案：检查控制台输出，调整 _parse_progress 方法。

Q6: 多线程下载卡住
原因：共享 aiohttp session 导致连接阻塞。

解决方案：为每个分块创建独立的 session。

Q7: 打包后程序无法启动
原因：缺少隐藏导入或资源文件。

解决方案：
```
# 添加隐藏导入
--hidden-import pydantic --hidden-import PIL

# 添加数据文件
--add-data "src;src" --add-data "config;config"
```
Q8: 中文文件名乱码
原因：Windows 控制台编码问题。

解决方案：
```
# 使用 gbk 编码写入批处理文件
with open('启动程序.bat', 'w', encoding='gbk') as f:
    f.write('@echo off\n')
```
版本历史
v1.0.0 (2024-03-30)
新增功能：

M3U8/HLS 下载支持

直链视频下载支持

YouTube、Bilibili 等网站支持

磁力链接、BT 种子支持

直播录制支持

图形界面

下载历史记录

自定义请求头

Cookie 导入

多线程下载

断点续传

技术栈：

PyQt6 图形界面

aiohttp 异步下载

N_m3u8DL-RE HLS 下载

yt-dlp 网站解析

aria2 P2P 下载

FFmpeg 格式转换

许可证
MIT License

Copyright (c) 2024 Video Downloader Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

免责声明
本工具仅供学习交流使用。使用者应遵守相关法律法规，尊重版权，仅下载有合法权利的内容。开发者不对因使用本工具产生的任何版权纠纷或法律问题承担责任。

