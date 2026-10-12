"""保存录像；OpenCV 无 H.264 编码器时由 FFmpeg 完成转换。"""

from pathlib import Path
import shutil
import subprocess

import cv2


def open_video_writer(filename, fps, size):
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    for codec in ('avc1', 'mp4v'):
        writer = cv2.VideoWriter(str(filename), cv2.VideoWriter_fourcc(*codec), fps, size)
        if writer.isOpened():
            return writer, codec
        writer.release()
    raise RuntimeError("无法创建录像文件，请检查编码器和录像目录写入权限")


def finalize_video(writer, filename, codec, browser_playable=False):
    writer.release()
    if not browser_playable or codec == 'avc1':
        return
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            ffmpeg = get_ffmpeg_exe()
        except (ImportError, RuntimeError):
            pass
    if not ffmpeg:
        raise RuntimeError("当前 OpenCV 不支持 H.264；请安装 FFmpeg 后重新分析视频")
    filename = Path(filename)
    converted = filename.with_name(filename.stem + '.h264.mp4')
    try:
        subprocess.run(
            [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(filename),
             '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
             '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-movflags', '+faststart', str(converted)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180,
        )
        converted.replace(filename)
    except (subprocess.SubprocessError, OSError):
        raise RuntimeError("录像转为浏览器支持的 H.264 格式失败") from None
    finally:
        if converted.exists():
            converted.unlink()
