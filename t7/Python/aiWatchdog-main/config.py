"""配置文件
包含视频监控系统的所有可配置参数
"""

from typing import Dict, Any
import logging
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = Path(os.environ.get("AI_STATE_DIR", str(BASE_DIR)))
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", str(BASE_DIR.parent.parent / "front" / "public")))
ABNORMAL_VIDEO_DIR = MEDIA_ROOT / "video" / "abnormal"
PICTURE_DIR = MEDIA_ROOT / "video" / "thumbnails"
TEMP_VIDEO_FILE = STATE_DIR / "output.mp4"


def parse_video_source(value):
    """纯整数使用本机摄像头，其他值作为文件路径或网络地址。"""
    value = str(value).strip()
    if not value:
        raise ValueError("VIDEO_SOURCE 不能为空")
    return int(value) if value.isdecimal() else value


def read_secret(name, default=""):
    if name in os.environ:
        return os.environ[name].strip()
    file_path = os.environ.get(name + "_FILE")
    if file_path:
        return Path(file_path).read_text(encoding="utf-8").strip()
    return default


VIDEO_SOURCE = parse_video_source(os.environ.get("VIDEO_SOURCE", "0"))

# 视频处理配置
class VideoConfig:
    VIDEO_INTERVAL = int(os.environ.get("VIDEO_INTERVAL", "1800"))  # 视频分段时长(秒)
    ANALYSIS_INTERVAL = int(os.environ.get("ANALYSIS_INTERVAL", "10"))  # 分析间隔(秒)
    BUFFER_DURATION = 11  # 滑窗分析时长（实际模型分析视频时长）#强制抽帧，每秒一帧率
    WS_RETRY_INTERVAL = 3  # WebSocket重连间隔(秒)
    MAX_WS_QUEUE = 100  # 消息队列最大容量
    JPEG_QUALITY = 70  # JPEG压缩质量



# API配置（环境变量优先，本地密钥文件不提交到Git）
_key_file = Path(__file__).with_name("api_keys.local.json")
_local_keys = {}
if not any(name in os.environ for name in ("DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY_FILE")) and _key_file.exists():
    _local_keys = json.loads(_key_file.read_text(encoding="utf-8"))


class APIConfig:
    DEEPSEEK_API_KEY = read_secret("DEEPSEEK_API_KEY", _local_keys.get("DEEPSEEK_API_KEY", ""))
    DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
    DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")

    REQUEST_TIMEOUT = 60.0  # 请求超时时间（秒）
    TEMPERATURE = 0.5
    TOP_P = 0.01

# RAG系统配置
class RAGConfig:
    # 知识库配置
    ENABLE_RAG = False
    VECTOR_API_URL = "http://172.16.10.44:8085/add_text/" # 启用RAG需要自行搭建rag服务，并构造相应api接口
    HISTORY_FILE = str(STATE_DIR / "video_histroy_info.txt")
    ALERT_LOG_FILE = str(STATE_DIR / "video_warning" / "alert_log.txt")


# 存档配置
ARCHIVE_DIR = str(STATE_DIR / "archive")


# 服务器配置
class ServerConfig:
    HOST = os.environ.get("AI_HOST", "0.0.0.0")
    PORT = int(os.environ.get("AI_PORT", "16532"))
    RELOAD = False
    WORKERS = 1


# 日志配置
LOG_CONFIG = {
    'level': logging.INFO,
    'format': '%(asctime)s - %(levelname)s - %(message)s',
    'handlers': [
        {'type': 'file', 'filename': str(STATE_DIR / 'code.log')},
        {'type': 'stream'}
    ]
}


def ensure_directories():
    for directory in (STATE_DIR, ABNORMAL_VIDEO_DIR, PICTURE_DIR,
                      Path(ARCHIVE_DIR), Path(RAGConfig.ALERT_LOG_FILE).parent):
        directory.mkdir(parents=True, exist_ok=True)


def update_config(args: Dict[str, Any]) -> None:
    """使用命令行参数更新配置
    
    Args:
        args: 包含命令行参数的字典
    """
    global VIDEO_SOURCE
    # 更新视频源
    if 'video_source' in args:
        VIDEO_SOURCE = parse_video_source(args['video_source'])
    
    # 更新视频处理配置
    for key in ['video_interval', 'analysis_interval', 'buffer_duration',
               'ws_retry_interval', 'max_ws_queue', 'jpeg_quality']:
        if key in args:
            setattr(VideoConfig, key.upper(), args[key])
    
    # 更新服务器配置
    for key in ['host', 'port', 'reload', 'workers']:
        if key in args:
            setattr(ServerConfig, key.upper(), args[key])
            
    # 更新API配置
    for key in ['deepseek_api_key', 'deepseek_api_url', 'deepseek_model',
               'request_timeout', 'temperature', 'top_p']:
        if key in args:
            setattr(APIConfig, key.upper(), args[key])
            
    # 更新RAG配置
    for key in ['enable_rag', 'vector_api_url', 'history_file',
               'history_save_interval']:
        if key in args:
            setattr(RAGConfig, key.upper(), args[key])


