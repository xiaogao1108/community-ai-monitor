"""智能视频监控服务：支持本机摄像头、挂载视频文件和网络摄像头。"""

import argparse
import asyncio
from collections import deque
from contextlib import asynccontextmanager, suppress
from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
import math
from pathlib import Path
import time

import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn

import config
from config import APIConfig, VideoConfig, ServerConfig, LOG_CONFIG, ARCHIVE_DIR
from django_integration import django_integration
from multi_modal_analyzer import MultiModalAnalyzer
from video_recording import open_video_writer, finalize_video


def parse_args():
    parser = argparse.ArgumentParser(description='智能视频监控系统')
    parser.add_argument('--video_source', help='摄像头整数编号、视频路径或 RTSP 地址')
    for name in ('video_interval', 'analysis_interval', 'buffer_duration',
                 'ws_retry_interval', 'max_ws_queue', 'jpeg_quality', 'port'):
        parser.add_argument('--' + name, type=int)
    parser.add_argument('--host')
    return {key: value for key, value in vars(parser.parse_args()).items() if value is not None}


class VideoProcessor:
    def __init__(self, video_source):
        self.video_source = video_source
        self.is_file = isinstance(video_source, str) and Path(video_source).is_file()
        self.cap = None
        self.archiver = None
        self.analyzer = None
        self.buffer = deque(maxlen=max(1, VideoConfig.BUFFER_DURATION))
        self.subscribers = set()
        self.analysis_task = None
        self._running = False
        self.state = 'starting'
        self.last_error = None
        self.frames_read = 0
        self.last_analysis_at = None
        self._last_analyzed_timestamp = None
        self._first_frame = None
        self.fps = 30.0

    def open_source(self):
        if not APIConfig.DEEPSEEK_API_KEY.strip():
            raise RuntimeError('请配置 DEEPSEEK_API_KEY 或 DEEPSEEK_API_KEY_FILE')
        if min(VideoConfig.ANALYSIS_INTERVAL, VideoConfig.VIDEO_INTERVAL, VideoConfig.BUFFER_DURATION) <= 0:
            raise ValueError('视频分段、分析间隔和缓冲时长必须大于零')
        if isinstance(self.video_source, str) and '://' in self.video_source:
            self.cap = cv2.VideoCapture(self.video_source, cv2.CAP_FFMPEG, [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000,
            ])
        else:
            self.cap = cv2.VideoCapture(self.video_source)
        success, frame = self.cap.read() if self.cap.isOpened() else (False, None)
        if not success or frame is None:
            self.cap.release()
            raise RuntimeError('无法读取 VIDEO_SOURCE；云服务器须配置挂载视频文件或可访问的摄像头地址')
        self._first_frame = frame
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.fps = fps if math.isfinite(fps) and fps > 0 else 30.0
        self.archiver = VideoArchiver(self.fps, (frame.shape[1], frame.shape[0]))
        self.analyzer = MultiModalAnalyzer()
        self._running = True
        self.state = 'running'

    async def start_processing(self):
        last_sample = 0.0
        last_analysis = time.monotonic()
        try:
            while self._running:
                started = time.monotonic()
                if self._first_frame is not None:
                    frame, self._first_frame = self._first_frame, None
                    success = True
                else:
                    success, frame = await asyncio.to_thread(self.cap.read)
                if not success or frame is None:
                    self.state = 'finishing' if self.is_file else 'failed'
                    if not self.is_file:
                        self.last_error = '视频流中断，请检查网络或摄像头并重启 AI 服务'
                    break
                self.frames_read += 1
                # 模型每秒使用一帧，避免在云服务器内存里堆积完整高清视频。
                if started - last_sample >= 1 or not self.buffer:
                    self.buffer.append({'frame': frame, 'timestamp': datetime.now().strftime('%Y-%m-%d-%H-%M-%S')})
                    last_sample = started
                await asyncio.to_thread(self.archiver.write_frame, frame)
                for queue in list(self.subscribers):
                    if queue.full():
                        queue.get_nowait()
                    queue.put_nowait(frame)
                if started - last_analysis >= VideoConfig.ANALYSIS_INTERVAL:
                    if self.analysis_task is None or self.analysis_task.done():
                        self.analysis_task = asyncio.create_task(self.trigger_analysis())
                        last_analysis = started
                await asyncio.sleep(max(0, 1 / self.fps - (time.monotonic() - started)))
            if self.analysis_task is not None:
                await self.analysis_task
            if (self._running and self.is_file and self.buffer
                    and self.buffer[-1]['timestamp'] != self._last_analyzed_timestamp):
                await self.trigger_analysis()
            if self.state == 'finishing':
                self.state = 'completed'
                logging.info('视频文件已分析完毕，不会自动循环；更换视频后请重启 AI 服务')
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.state = 'failed'
            self.last_error = '视频处理失败: ' + type(error).__name__
            logging.error(self.last_error)
        finally:
            self._running = False
            if self.cap is not None:
                self.cap.release()
            if self.archiver is not None:
                self.archiver.close()
            for queue in list(self.subscribers):
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(None)

    async def trigger_analysis(self):
        clip = list(self.buffer)
        if not clip:
            return
        self._last_analyzed_timestamp = clip[-1]['timestamp']
        try:
            result = await self.analyzer.analyze(
                [item['frame'] for item in clip], 1.0,
                (clip[0]['timestamp'], clip[-1]['timestamp']),
            )
            self.last_analysis_at = datetime.now().isoformat()
            if self.state != 'failed':
                self.last_error = None
            if result['alert'] != '无异常':
                await AlertService.notify(result)
        except Exception as error:
            self.last_error = '模型分析或告警入库失败: ' + type(error).__name__
            logging.error(self.last_error)

    def health(self):
        healthy = self.state in ('running', 'finishing', 'completed') and self.last_error is None
        return {
            'status': self.state,
            'healthy': healthy,
            'source_type': 'file' if self.is_file else 'camera_or_stream',
            'frames_read': self.frames_read,
            'last_analysis_at': self.last_analysis_at,
            'error': self.last_error,
        }

    async def video_streamer(self, websocket):
        queue = asyncio.Queue(maxsize=2)
        self.subscribers.add(queue)
        try:
            while self._running:
                frame = await queue.get()
                if frame is None:
                    break
                success, encoded = await asyncio.to_thread(
                    cv2.imencode, '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), VideoConfig.JPEG_QUALITY],
                )
                if success:
                    await websocket.send_bytes(encoded.tobytes())
        finally:
            self.subscribers.discard(queue)


class AlertService:
    _connections = set()

    @classmethod
    async def register(cls, websocket):
        await websocket.accept()
        cls._connections.add(websocket)

    @classmethod
    async def notify(cls, data):
        message = json.dumps({'timestamp': datetime.now().isoformat(), **data}, ensure_ascii=False)
        for connection in list(cls._connections):
            try:
                await asyncio.wait_for(connection.send_text(message), timeout=5)
            except Exception:
                cls._connections.discard(connection)


class VideoArchiver:
    def __init__(self, fps, size):
        self.fps = fps
        self.size = size
        self.current_writer = None
        self.last_split = 0.0

    def write_frame(self, frame):
        if self.current_writer is None or time.monotonic() - self.last_split >= VideoConfig.VIDEO_INTERVAL:
            self.close()
            self.filename = Path(ARCHIVE_DIR) / (datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.mp4')
            self.current_writer, self.codec = open_video_writer(self.filename, self.fps, self.size)
            self.last_split = time.monotonic()
        self.current_writer.write(frame)

    def close(self):
        if self.current_writer is not None:
            finalize_video(self.current_writer, self.filename, self.codec)
            self.current_writer = None


@asynccontextmanager
async def lifespan(app):
    config.ensure_directories()
    handlers = [RotatingFileHandler(LOG_CONFIG['handlers'][0]['filename'], maxBytes=10 * 1024 * 1024,
                                    backupCount=3, encoding='utf-8'), logging.StreamHandler()]
    logging.basicConfig(
        level=LOG_CONFIG['level'], format=LOG_CONFIG['format'],
        handlers=handlers,
    )
    processor = VideoProcessor(config.VIDEO_SOURCE)
    app.state.processor = processor
    task = None
    try:
        await asyncio.to_thread(processor.open_source)
        task = asyncio.create_task(processor.start_processing())
        yield
    finally:
        processor._running = False
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=15)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()
        if processor.analysis_task is not None:
            processor.analysis_task.cancel()
            with suppress(asyncio.CancelledError):
                await processor.analysis_task
        await django_integration.close()
        for handler in handlers:
            logging.getLogger().removeHandler(handler)
            handler.close()


app = FastAPI(title='智能视频监控系统', lifespan=lifespan)


@app.get('/health/')
async def health():
    processor = getattr(app.state, 'processor', None)
    data = processor.health() if processor else {'status': 'starting', 'healthy': False}
    return JSONResponse(data, status_code=200 if data['healthy'] else 503)


@app.websocket('/alerts')
async def alert_websocket(websocket: WebSocket):
    await AlertService.register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        AlertService._connections.discard(websocket)


@app.websocket('/video_feed')
async def video_feed(websocket: WebSocket):
    await websocket.accept()
    try:
        await app.state.processor.video_streamer(websocket)
    except WebSocketDisconnect:
        pass
    finally:
        with suppress(RuntimeError):
            await websocket.close()


if __name__ == '__main__':
    config.update_config(parse_args())
    uvicorn.run(app, host=ServerConfig.HOST, port=ServerConfig.PORT, reload=False, workers=1)
