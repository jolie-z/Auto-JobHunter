#!/usr/bin/env python3
"""
记忆中枢 (Memory Manager) - Project Polaris AI 模块的持久化记忆管理器

功能：
1. 集中管理 Mem0 实例
2. 提供记忆检索和添加的封装函数
3. 支持用户偏好、避坑指南、写作风格等持久化记忆
"""

from mem0 import Memory
import os
from common.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

# 🌟 强行将百炼的地址注入到系统的环境变量中
os.environ["OPENAI_BASE_URL"] = OPENAI_BASE_URL
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# 🌟 初始化 Mem0 实例
# 如果使用非 OpenAI 模型（如 DeepSeek），需要配置 llm 参数
config = {
    "vector_store": {
        "provider": "chroma", 
        "config": {
            "collection_name": "jobs_aliyun", 
            "path": "./chroma_mem0_db"  # 存在当前目录，肉眼可见
        }
    },
    "llm": {
        "provider": "openai",
        "config": {
            "model": OPENAI_MODEL,
            "api_key": OPENAI_API_KEY,
            #"base_url": OPENAI_BASE_URL,
            "temperature": 0.1
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-v3", # 阿里云百炼的专属向量模型
            "embedding_dims": 1024
        }
    }
}

# 实例化 Memory
m = Memory.from_config(config)


def get_relevant_memories(query, user_id="jolie", limit=5):
    """
    获取与查询相关的记忆
    
    Args:
        query (str): 查询字符串（如岗位名称 + JD 描述片段）
        user_id (str): 用户 ID，默认为 "jolie"
        limit (int): 返回的记忆数量上限
    
    Returns:
        str: 拼接后的记忆字符串，如果没有记忆则返回空字符串
    """
    try:
        # 搜索相关记忆
        memories = m.search(query, user_id=user_id, limit=limit)
        
        # 🌟 防御性解析：处理不同的返回格式
        # 如果返回的本身就是个字典，尝试提取其中的列表
        if isinstance(memories, dict):
            memories = memories.get("results", []) or memories.get("memories", [memories])
        
        if not memories or len(memories) == 0:
            return ""
        
        # 🌟 极其鲁棒的记忆文本提取逻辑
        context_list = []
        for idx, mem in enumerate(memories, 1):
            memory_text = ""
            
            if isinstance(mem, dict):
                # 如果是字典，安全获取 'memory' 字段
                memory_text = str(mem.get('memory', mem))
            elif isinstance(mem, str):
                # 如果直接是字符串，直接使用
                memory_text = mem
            elif hasattr(mem, 'memory'):
                # 如果是 Pydantic 对象或其他带 memory 属性的对象
                memory_text = str(mem.memory)
            else:
                # 兜底：强制转字符串
                memory_text = str(mem)
            
            # 只添加非空的记忆文本
            if memory_text and memory_text.strip():
                context_list.append(f"{idx}. {memory_text}")
        
        if not context_list:
            return ""
        
        return "\n".join(context_list)
    
    except Exception as e:
        print(f"⚠️ 获取记忆失败: {e}")
        return ""


def add_memory(text, user_id="jolie"):
    """
    添加新记忆
    
    Args:
        text (str): 记忆内容
        user_id (str): 用户 ID，默认为 "jolie"
    
    Returns:
        bool: 是否添加成功
    """
    try:
        m.add(text, user_id=user_id)
        return True
    except Exception as e:
        print(f"❌ 添加记忆失败: {e}")
        return False


# 暴露 Memory 实例供外部直接使用
__all__ = ['m', 'get_relevant_memories', 'add_memory']
