#!/usr/bin/env python3
"""Build executable for Video Downloader GUI."""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def clean():
    """Clean build directories."""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        path = Path(dir_name)
        if path.exists():
            shutil.rmtree(path)
            print(f"Removed {path}")
    
    # Clean .pyc files
    for pycache in Path('.').rglob('__pycache__'):
        shutil.rmtree(pycache)
        print(f"Removed {pycache}")


def install_dependencies():
    """Install required dependencies."""
    print("Installing dependencies...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)


def build():
    """Build executable with PyInstaller."""
    print("Building executable...")
    
    # 使用 spec 文件打包
    cmd = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', 'build_exe.spec']
    subprocess.run(cmd, check=True)
    
    print("Build completed!")


def create_portable():
    """Create portable zip archive."""
    print("Creating portable archive...")
    
    dist_dir = Path('dist')
    exe_path = dist_dir / 'VideoDownloader.exe'
    
    if not exe_path.exists():
        print(f"Error: {exe_path} not found")
        return
    
    portable_dir = dist_dir / 'VideoDownloader_Portable'
    
    if portable_dir.exists():
        shutil.rmtree(portable_dir)
    portable_dir.mkdir(parents=True)
    
    # 复制可执行文件
    shutil.copy(exe_path, portable_dir / 'VideoDownloader.exe')
    
    # 复制配置文件
    if Path('config').exists():
        shutil.copytree('config', portable_dir / 'config', dirs_exist_ok=True)
    
    # 复制资源文件
    if Path('resources').exists():
        shutil.copytree('resources', portable_dir / 'resources', dirs_exist_ok=True)
    
    # 创建启动脚本
    with open(portable_dir / '启动程序.bat', 'w', encoding='gbk') as f:
        f.write('@echo off\n')
        f.write('echo Video Downloader\n')
        f.write('echo ================\n')
        f.write('echo.\n')
        f.write('start VideoDownloader.exe\n')
        f.write('echo.\n')
    
    # 创建 zip
    shutil.make_archive(str(dist_dir / 'VideoDownloader_Portable'), 'zip', dist_dir, 'VideoDownloader_Portable')
    print(f"Created portable archive at {dist_dir / 'VideoDownloader_Portable.zip'}")


def create_installer():
    """Create NSIS installer script (optional)."""
    nsis_script = '''
    ; Video Downloader NSIS Installer Script
    ; Run with: makensis installer.nsi

    !define APP_NAME "Video Downloader"
    !define APP_VERSION "1.0.0"
    !define APP_PUBLISHER "Video Downloader Team"
    !define APP_EXE "VideoDownloader.exe"

    Name "${APP_NAME}"
    OutFile "dist/VideoDownloader_Setup.exe"
    InstallDir "$PROGRAMFILES\\${APP_NAME}"
    RequestExecutionLevel admin

    !include "MUI2.nsh"

    !insertmacro MUI_PAGE_WELCOME
    !insertmacro MUI_PAGE_DIRECTORY
    !insertmacro MUI_PAGE_INSTFILES
    !insertmacro MUI_PAGE_FINISH

    !insertmacro MUI_LANGUAGE "SimpChinese"

    Section "Main Application"
        SetOutPath "$INSTDIR"
        File "dist\\${APP_EXE}"
        File /r "config"
        CreateDirectory "$SMPROGRAMS\\${APP_NAME}"
        CreateShortCut "$SMPROGRAMS\\${APP_NAME}\\${APP_NAME}.lnk" "$INSTDIR\\${APP_EXE}"
        CreateShortCut "$DESKTOP\\${APP_NAME}.lnk" "$INSTDIR\\${APP_EXE}"
    SectionEnd

    Section "Uninstall"
        Delete "$INSTDIR\\${APP_EXE}"
        RMDir /r "$INSTDIR\\config"
        RMDir "$INSTDIR"
        Delete "$SMPROGRAMS\\${APP_NAME}\\${APP_NAME}.lnk"
        RMDir "$SMPROGRAMS\\${APP_NAME}"
        Delete "$DESKTOP\\${APP_NAME}.lnk"
    SectionEnd
    '''
    
    with open('installer.nsi', 'w', encoding='utf-8') as f:
        f.write(nsis_script)
    print("Created installer.nsi (run with makensis to create installer)")


def main():
    """Main build process."""
    print("=" * 60)
    print("Video Downloader - Build Script")
    print("=" * 60)
    
    # 解析参数
    if len(sys.argv) > 1:
        if sys.argv[1] == 'clean':
            clean()
            return
        elif sys.argv[1] == 'install':
            install_dependencies()
            return
        elif sys.argv[1] == 'portable':
            create_portable()
            return
    
    # 完整构建
    clean()
    install_dependencies()
    build()
    create_portable()
    
    print("\n" + "=" * 60)
    print("Build completed successfully!")
    print(f"Executable: dist/VideoDownloader.exe")
    print(f"Portable: dist/VideoDownloader_Portable.zip")
    print("=" * 60)


if __name__ == "__main__":
    main()