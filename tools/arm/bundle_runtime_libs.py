# -*- coding: utf-8 -*-
"""打包后运行库闭包收集（Linux 容器内运行）。

扫描 _internal 下 Qt/gstreamer 相关 .so 的 ldd 依赖，把落在系统路径、
且不在 glibc 白名单内的库复制进 _internal，循环直至闭包完整。
解决目标机缺少 libnsl.so.2 / gstreamer 等组件导致的启动失败。

用法：python tools/arm/bundle_runtime_libs.py <路径>/PhotoManager/_internal
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

# 目标机（麒麟 V10 / 常见 Linux 桌面）基本必备，不再重复打包
WHITELIST = re.compile(
    r"/(ld-linux|libc\.so|libm\.so|libdl\.so|libpthread|librt\.so|libresolv"
    r"|libgcc_s|libstdc\+\+|libz\.so|libglib-2\.0|libgobject-2\.0"
    r"|libgmodule-2\.0|libgio-2\.0)"
)


MISSING = set()


def ldd_deps(path: Path):
    out = subprocess.run(["ldd", str(path)], capture_output=True, text=True).stdout
    deps = []
    for line in out.splitlines():
        line = line.strip()
        if "=>" in line:
            name, rest = line.split("=>", 1)
            rest = rest.strip()
            if rest.startswith("not found"):
                MISSING.add(name.strip())  # 容器里也缺的库，汇报但不阻塞
                continue
            deps.append(Path(rest.split(" ")[0]))
        elif line.startswith("/"):
            deps.append(Path(line.split(" ")[0]))
    return deps


def scan_files(internal: Path):
    patterns = ["PySide6/Qt/lib/*.so*", "PySide6/Qt/qml/**/*.so*",
                "PySide6/Qt/plugins/**/*.so*", "gstreamer-1.0/*.so"]
    for pat in patterns:
        yield from internal.glob(pat)


def main():
    internal = Path(sys.argv[1]).resolve()
    if not internal.is_dir():
        print(f"目录不存在: {internal}")
        return 1
    copied = set()
    for round_no in range(1, 4):  # 新库可能再带新依赖，闭包最多三轮
        new = []
        for so in sorted(scan_files(internal)):
            for dep in ldd_deps(so):
                if WHITELIST.search(str(dep)):
                    continue
                target = internal / dep.name
                if target.exists():
                    continue
                if str(dep) in copied:
                    continue
                shutil.copy2(dep, target)
                copied.add(str(dep))
                new.append(dep.name)
        print(f"第 {round_no} 轮: 新打包 {len(new)} 个系统库")
        if not new:
            break
    print("已打包的系统库:")
    for name in sorted(copied):
        print("  ", name)
    print(f"合计 {len(copied)} 个。闭包完成。")
    if MISSING:
        print("⚠️ 容器内也缺失、无法打包的库（需关注目标机是否自带）:")
        for m in sorted(MISSING):
            print("  ", m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
