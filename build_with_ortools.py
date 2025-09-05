#!/usr/bin/env python3
"""
专门处理OR-Tools依赖的打包脚本
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def find_ortools_path():
    """查找OR-Tools安装路径（优先使用虚拟环境）"""
    # 首先尝试虚拟环境
    venv_python = os.path.join(os.getcwd(), 'PUMC_venv', 'Scripts', 'python.exe')
    if os.path.exists(venv_python):
        try:
            result = subprocess.run([venv_python, '-c', 'import ortools; import os; print(os.path.dirname(ortools.__file__))'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                ortools_path = Path(result.stdout.strip())
                print(f"Found OR-Tools in virtual environment at: {ortools_path}")
                return ortools_path
        except Exception as e:
            print(f"Failed to check virtual environment: {e}")

    # 回退到当前环境
    try:
        import ortools
        ortools_path = Path(ortools.__file__).parent
        print(f"Found OR-Tools in current environment at: {ortools_path}")
        return ortools_path
    except ImportError:
        print("ERROR: OR-Tools not found in any environment")
        return None

def create_spec_with_ortools():
    """创建包含OR-Tools的spec文件"""
    ortools_path = find_ortools_path()
    if not ortools_path:
        return False
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 只包含OR-Tools，不包含文档文件
        (r'{ortools_path}', 'ortools'),
    ],
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtGui', 
        'PyQt5.QtWidgets',
        'pandas',
        'numpy',
        'openpyxl',
        'ortools',
        'ortools.sat',
        'ortools.sat.python',
        'ortools.sat.python.cp_model',
        'ortools.linear_solver',
        'ortools.constraint_solver',
        'ortools.util',
        'ortools.algorithms',
        'ortools.graph',
        'ortools.init',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'streamlit',
        'plotly',
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'pytest',
        'pytest-cov',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PUMC_Course_Scheduling',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='PUMClogo.ico',  # 添加图标文件
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PUMC_Course_Scheduling'
)
'''
    
    with open('PUMC_with_ortools.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("Created PUMC_with_ortools.spec")
    return True

def build_with_pyinstaller():
    """使用PyInstaller打包"""
    print("Starting PyInstaller build...")
    
    # 清理旧文件
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists('build'):
        shutil.rmtree('build')
    
    # 使用虚拟环境的Python运行PyInstaller
    venv_python = os.path.join(os.getcwd(), 'PUMC_venv', 'Scripts', 'python.exe')
    if os.path.exists(venv_python):
        cmd = [venv_python, '-m', 'PyInstaller', 'PUMC_with_ortools.spec']
        print(f"Using virtual environment Python: {venv_python}")
    else:
        cmd = [sys.executable, '-m', 'PyInstaller', 'PUMC_with_ortools.spec']
        print(f"Using system Python: {sys.executable}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ PyInstaller build completed successfully")
        return True
    else:
        print("❌ PyInstaller build failed:")
        print(result.stderr)
        return False

def copy_ortools_manually():
    """手动复制OR-Tools文件到打包目录"""
    ortools_path = find_ortools_path()
    if not ortools_path:
        return False
    
    dist_path = Path('dist/PUMC_Course_Scheduling')
    if not dist_path.exists():
        print("ERROR: dist directory not found")
        return False
    
    target_ortools = dist_path / 'ortools'
    
    print(f"Copying OR-Tools from {ortools_path} to {target_ortools}")
    
    try:
        if target_ortools.exists():
            shutil.rmtree(target_ortools)
        shutil.copytree(ortools_path, target_ortools)
        print("✅ OR-Tools files copied successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to copy OR-Tools: {e}")
        return False

def test_built_app():
    """测试打包后的应用"""
    exe_path = Path('dist/PUMC_Course_Scheduling/PUMC_Course_Scheduling.exe')
    if not exe_path.exists():
        print("ERROR: Built executable not found")
        return False
    
    print("Testing built application...")
    # 这里可以添加更多测试逻辑
    print("✅ Built application found")
    return True

def main():
    """主函数"""
    print("=== OR-Tools PyInstaller Build Script ===")
    
    # 1. 检查OR-Tools
    if not find_ortools_path():
        return False
    
    # 2. 创建spec文件
    if not create_spec_with_ortools():
        return False
    
    # 3. 运行PyInstaller
    if not build_with_pyinstaller():
        return False
    
    # 4. 手动复制OR-Tools（双重保险）
    if not copy_ortools_manually():
        print("WARNING: Manual OR-Tools copy failed, but build may still work")
    
    # 5. 测试结果
    if not test_built_app():
        return False
    
    print("\n🎉 Build completed successfully!")
    print("📦 Executable: dist/PUMC_Course_Scheduling/PUMC_Course_Scheduling.exe")
    print("💡 Try running the executable to test OR-Tools integration")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n💥 Build failed!")
        sys.exit(1)
