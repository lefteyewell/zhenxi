# 视频管理 V2 · 麒麟 aarch64 gstreamer 验证清单

> 目的：V2 内嵌播放（QtMultimedia `MediaPlayer`+`VideoOutput`）在**银河麒麟 V10 aarch64** 上依赖
> **gstreamer 1.0** 后端。本清单用于在真机判定「内嵌播放是否可用」，并作为 V2 在该平台的验收门槛。
> 关键前提：V2 设计为「内嵌优先 + 系统播放器兜底」——即便本清单判定不可用，也**仅回退到系统播放器，
> 不劣于 V1**，不会破坏功能。

## 1. Qt 后端判定
Qt Multimedia 在 Linux 使用 gstreamer 1.0（非 WMF/ffmpeg——那是 Windows 后端）。
- 若 `QT_MEDIA_BACKEND=gstreamer`（默认）且系统有 gstreamer 1.0 → 走内嵌。
- 若 gstreamer 或编解码缺失 → `MediaPlayer` 加载/播放失败 → 触发兜底（系统播放器）。

## 2. 关键元件探测（必须全部有）
```sh
gst-inspect-1.0 --version                      # gstreamer 是否安装
gst-inspect-1.0 playbin >/dev/null && echo OK  # 播放管线
gst-inspect-1.0 qtdemux  >/dev/null && echo OK # MP4/MOV 解复用
gst-inspect-1.0 avdec_h264 >/dev/null && echo OK  # H.264 解码（来自 gstreamer1.0-libav）
gst-inspect-1.0 avdec_aac  >/dev/null && echo OK  # AAC 音频解码
gst-inspect-1.0 vp8dec >/dev/null && echo OK      # WebM（VP8）解码
gst-inspect-1.0 vp9dec >/dev/null && echo OK      # WebM（VP9）解码
```
判定：`playbin/qtdemux/avdec_h264/avdec_aac` 必须有；`vp8dec/vp9dec` 决定 WebM 是否可内嵌播放。
缺任一项 → 对应容器/编码无法内嵌播放（走兜底）。

## 3. 试播一条真实样本
```sh
gst-launch-1.0 -q playbin uri=file:///absolute/path/to/sample.mp4
# 能出声/出画且进程不报 "no decoder" 即通过
```

## 4. 安装缺失组件（按包管理器二选一）
麒麟 V10 多为 RPM/dnf 系；若为 apt 系用右侧。
```sh
# dnf / yum
sudo dnf install gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good \
                 gstreamer1-plugins-bad gstreamer1-plugins-ugly gstreamer1-libav
# apt / apt-get
sudo apt install gstreamer1.0-tools gstreamer1.0-plugins-base \
                 gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
                 gstreamer1.0-plugins-ugly gstreamer1.0-libav
```
> `gstreamer1-libav`（或 libav 插件）是 H.264/AAC 解码的关键，最常见缺失项。
> 麒麟若源里没有 libav，可试 `gstreamer1.0-plugins-bad`/`ugly` 或系统自带的多媒体编解码包。

## 5. 应用层验证（跑 V2 后）
1. 导入含 MP4 的文件夹 → 网格出现 ▶ 徽标 + 时长。
2. 信息面板点「▶ 播放」/双击缩略图 → 内嵌播放器是否出声出画。
3. 若内嵌失败：应显示提示 + 「用系统播放器打开」按钮，点击后系统播放器能播（兜底生效）。

## 6. 验收标准
- [ ] `playbin/qtdemux/avdec_h264/avdec_aac` 均在（第 2 节）
- [ ] `gst-launch playbin` 试播 MP4 通过（第 3 节）
- [ ] 应用内 MP4 内嵌播放成功；失败时兜底按钮可用（第 5 节）
- [ ] 记录实际缺失/需额外安装的包，回填到本文档与 MEMORY
