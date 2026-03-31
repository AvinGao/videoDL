#!/usr/bin/env python3
"""调试 HLS 下载引擎的参数传递"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core.engines.hls import HlsEngine
from src.core.models.download import DownloadOptions
from src.core.models.headers import RequestHeaders


async def debug():
    url = "https://surrit.com/32c61abd-2cce-4ff2-8554-238627d20636/720p/video.m3u8"
    
    # 设置请求头 - 与命令行成功的一致
    headers = RequestHeaders(
        referer="https://missav.ws/cn/dldss-478",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    options = DownloadOptions(
        save_dir=Path("./downloads"),
        save_name="test_output",
        thread_count=8,
        retry_count=3,
        output_format="mp4"
    )
    
    engine = HlsEngine()
    
    # 手动调用并打印命令
    print("=" * 60)
    print("调试信息:")
    print(f"URL: {url}")
    print(f"请求头: {headers.to_dict()}")
    print(f"选项: save_dir={options.save_dir}, save_name={options.save_name}, thread_count={options.thread_count}")
    print("=" * 60)
    
    # 执行下载
    result = await engine.download(url, options, headers)
    
    if result.success:
        print(f"\n✓ 下载成功: {result.file_path}")
        print(f"  大小: {result.file_size_bytes / (1024*1024):.2f} MB")
    else:
        print(f"\n✗ 下载失败: {result.error_message}")


if __name__ == "__main__":
    asyncio.run(debug())