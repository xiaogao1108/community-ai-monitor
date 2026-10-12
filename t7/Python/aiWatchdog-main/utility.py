# -*- coding: utf-8 -*-
"""
Created on Tue Mar  4 10:50:52 2025

@author: 18523
"""
import base64
import asyncio
import requests
import cv2 
import time 
import numpy as np
import json
import httpx
from config import APIConfig, RAGConfig, VideoConfig, TEMP_VIDEO_FILE
from video_recording import open_video_writer, finalize_video



def frames_to_base64(frames,fps,timestamps):
    width = frames[0].shape[1]
    height = frames[0].shape[0]    
    video_writer, codec = open_video_writer(TEMP_VIDEO_FILE, fps, (width, height))
    # 遍历所有帧，并将其写入视频文件
    for frame in frames:
        # 确保帧是正确的数据类型和形状
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
        if len(frame.shape) == 2:
            # 如果帧是灰度的，转换为BGR
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        video_writer.write(frame)
    
    # 释放VideoWriter对象
    finalize_video(video_writer, TEMP_VIDEO_FILE, codec, browser_playable=True)

    
    with open(TEMP_VIDEO_FILE, 'rb') as video_file:
        video_base64 = base64.b64encode(video_file.read()).decode('utf-8')
    
    return video_base64


# 抽取关键帧，通过DeepSeek图像接口分析；录像仍用于异常存档。
async def video_chat_async_limit_frame(text, frames, timestamps, fps=20):
    if not frames:
        raise ValueError("没有可分析的视频帧")
    if not APIConfig.DEEPSEEK_API_KEY.strip():
        raise ValueError("请配置 DEEPSEEK_API_KEY 或 api_keys.local.json")

    await asyncio.to_thread(frames_to_base64, frames, fps, timestamps)
    frame_count = min(len(frames), max(1, int(VideoConfig.BUFFER_DURATION)))
    content = [{"type": "text", "text": text}]
    for i in range(frame_count):
        index = i * (len(frames) - 1) // max(1, frame_count - 1)
        success, encoded = cv2.imencode('.jpg', frames[index])
        if not success:
            raise ValueError("视频帧JPEG编码失败")
        image_base64 = base64.b64encode(encoded.tobytes()).decode('utf-8')
        content.append({
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64," + image_base64}
        })
    return await chat_request(content)


async def video_chat_async(text, frames, timestamps, fps=20):
    return await video_chat_async_limit_frame(text, frames, timestamps, fps)


async def chat_request(message, stream=False):
    if stream:
        raise ValueError("监控分析需要完整结果，暂不支持流式响应")
    api_key = APIConfig.DEEPSEEK_API_KEY.strip()
    if not api_key:
        raise ValueError("请配置 DEEPSEEK_API_KEY 或 api_keys.local.json")
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key
    }
    data = {
        "messages": [{"role": "user", "content": message}],
        "model": APIConfig.DEEPSEEK_MODEL,
        "temperature": APIConfig.TEMPERATURE,
        "top_p": APIConfig.TOP_P,
        "thinking": {"type": "disabled"},
        "stream": False
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(APIConfig.REQUEST_TIMEOUT)) as client:
        response = await client.post(APIConfig.DEEPSEEK_API_URL, headers=headers, json=data)
        response.raise_for_status()
        try:
            content = response.json()['choices'][0]['message']['content']
        except (ValueError, KeyError, IndexError, TypeError):
            raise ValueError("DeepSeek返回格式异常，未获取到分析文本") from None
        if not isinstance(content, str) or not content.strip():
            raise ValueError("DeepSeek返回了空的分析文本")
        return content


def insert_txt(docs,table_name):
    #插入文本，同时向量化
    url = RAGConfig.VECTOR_API_URL
    """docs = [
        "Artificial intelligence was founded as an academic discipline in 1956.",
        "The field of AI research was founded at a workshop held on the campus of Dartmouth College during the summer of 1956."
    ]"""
    data = {
        "docs": docs,
        "table_name": table_name
    }
    response = requests.post(url, json=data)
    return response.json()
