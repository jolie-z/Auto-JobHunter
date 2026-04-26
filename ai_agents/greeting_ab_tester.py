import os
import sys
import time
import requests
from openai import OpenAI

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from common.feishu_api import get_pending_apply_jobs, get_tenant_access_token, extract_feishu_text
# 🌟 1. 从配置中心导入大模型配置与飞书相关变量
from common.config import (
    LLM_API_KEY, 
    LLM_BASE_URL, 
    OPENAI_MODEL, 
    FEISHU_APP_TOKEN, 
    FEISHU_TABLE_ID_JOBS,
    FEISHU_TABLE_ID_PROMPTS,
    FEISHU_TABLE_ID_RESUMES
)

# 🌟 2. 初始化客户端
client = OpenAI(
    api_key=LLM_API_KEY, 
    base_url=LLM_BASE_URL
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==========================================
# 🌟 新增：动态从飞书拉取 Prompt 和简历的引擎
# ==========================================
def get_active_prompt_from_feishu(keyword: str, fallback_prompt: str) -> str:
    try:
        token = get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID_PROMPTS}/records/search"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "filter": {
                "conjunction": "and",
                "conditions": [{"field_name": "当前状态", "operator": "is", "value": ["启用"]}]
            }
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        items = resp.json().get("data", {}).get("items", [])
        
        for item in items:
            name = extract_feishu_text(item.get("fields", {}).get("策略名称", ""))
            content = extract_feishu_text(item.get("fields", {}).get("Prompt内容", ""))
            if keyword in name:
                print(f"✅ 成功加载云端策略: {name}")
                return content
                
        print(f"⚠️ 未找到包含关键字 '{keyword}' 的启用策略，将使用默认兜底策略。")
        return fallback_prompt
    except Exception as e:
        print(f"❌ 拉取云端策略失败 ({keyword}): {e}")
        return fallback_prompt

def load_resume():
    print("☁️ 正在从飞书云端寻找【启用】状态的简历...")
    try:
        token = get_tenant_access_token()
        if not token:
            print("❌ 获取飞书 Token 失败，无法读取云端简历")
            return None
            
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID_RESUMES}/records/search"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "filter": {
                "conjunction": "and",
                "conditions": [{"field_name": "当前状态", "operator": "is", "value": ["启用"]}]
            }
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        items = resp.json().get("data", {}).get("items", [])
        
        if items:
            resume_text = extract_feishu_text(items[0].get("fields", {}).get("简历内容", ""))
            if resume_text.strip():
                print(f"✅ 云端简历读取成功，共 {len(resume_text)} 字符")
                return resume_text
        print("❌ 未在飞书中找到处于【启用】状态的简历！")
        return None
    except Exception as e:
        print(f"❌ 读取云端简历出错: {e}")
        return None

def update_greeting_only(record_id, greeting):
    """【专用接口】只更新打招呼语，绝对不碰定制简历的字段"""
    token = get_tenant_access_token()
    if not token:
        return False

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID_JOBS}/records/{record_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "fields": {
            "打招呼语": greeting,
            "跟进状态": "待人工复核" 
        }
    }
    
    try:
        response = requests.put(url, headers=headers, json=payload)
        return response.json().get("code") == 0
    except Exception:
        return False

def generate_new_greeting(resume_text, jd_text):
    """只生成打招呼语，连接飞书大脑"""
    # 🌟 灵魂：从飞书拉取策略逻辑
    soul_prompt = get_active_prompt_from_feishu(
        keyword="开场", 
        fallback_prompt="你是一位资深猎头兼高情商求职专家。请根据简历和JD撰写打招呼语。"
    )
    
    # 🌟 肉体：锁死文本约束
    body_format = "【格式要求】：严格控制在100-200字之间。请直接输出打招呼语的纯文本，绝不能包含任何解释或前缀。"
    
    new_greeting_prompt = f"{soul_prompt}\n\n{body_format}\n\n【我的个人简历】：\n{resume_text}\n\n【目标岗位JD】：\n{jd_text}"

    try:
        print("      🧠 正在用云端 Prompt 构思打招呼语...")
        response = client.chat.completions.create(
            model=OPENAI_MODEL,  # 统一使用配置模型
            messages=[{"role": "user", "content": new_greeting_prompt}],
            temperature=0.8 
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"      ❌ 生成失败: {e}")
        return None

def run_greeting_test():
    print("🚀 启动【打招呼语 A/B 测试引擎】...\n")
    
    base_resume = load_resume()
    if not base_resume:
        print("❌ 找不到启用的简历，退出。")
        return

    print("📡 正在扫描飞书，寻找状态为【准备投递】的目标...")
    target_jobs = get_pending_apply_jobs()
    
    if not target_jobs:
        print("🤷‍♂️ 没有找到【准备投递】的岗位。")
        return
        
    print(f"✅ 发现 {len(target_jobs)} 个岗位！开始批量重写打招呼语...\n")

    for i, job in enumerate(target_jobs):
        print(f"{'='*40}")
        print(f"🎯 [{i+1}/{len(target_jobs)}] 正在处理: {job['company']} - {job['job_title']}")
        
        new_greeting = generate_new_greeting(base_resume, job['jd_text'])
        
        if new_greeting:
            print(f"      ✨ 新话术预览: {new_greeting}")
            is_success = update_greeting_only(job['record_id'], new_greeting)
            if is_success:
                print("      🚀 写入飞书成功！")
            else:
                print("      ❌ 写入失败。")
        time.sleep(2)
        
    print("\n🏁 所有新版打招呼语已更新完毕！")

if __name__ == "__main__":
    run_greeting_test()