import os
import sys
import json
import re
import requests
from typing import List, Dict
from openai import OpenAI

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 🌟 1. 从配置中心导入统一的大模型配置与飞书变量
from common.config import (
    OPENAI_MODEL,
    FEISHU_APP_TOKEN,
    FEISHU_TABLE_ID_PROMPTS,
    get_openai_client,
    get_serper_api_key,
)
# 🌟 2. 导入记忆管理器和飞书接口
from memory_manager import get_relevant_memories
from common import feishu_api

# ==========================================
# 🌟 新增：动态从飞书拉取 Prompt 的引擎
# ==========================================
def get_active_prompt_from_feishu(keyword: str, fallback_prompt: str) -> str:
    """
    根据关键字（如"评估"、"改写"、"开场白"）去飞书拉取当前处于【启用】状态的 Prompt
    """
    try:
        token = feishu_api.get_tenant_access_token()
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
        
        # 遍历启用的策略，找名字里包含对应关键字的
        for item in items:
            name = feishu_api.extract_feishu_text(item.get("fields", {}).get("策略名称", ""))
            content = feishu_api.extract_feishu_text(item.get("fields", {}).get("Prompt内容", ""))
            if keyword in name:
                print(f"✅ 成功加载云端策略: {name}")
                return content
                
        print(f"⚠️ 未找到包含关键字 '{keyword}' 的启用策略，将使用默认兜底策略。")
        return fallback_prompt
    except Exception as e:
        print(f"❌ 拉取云端策略失败 ({keyword}): {e}")
        return fallback_prompt


# ==========================================
# 任务 1：岗位深度评估 (JSON)
# ==========================================
def get_job_match_score(resume_text, jd_text, job_name=""):
    memory_query = f"{job_name} {jd_text[:200]}" if job_name else jd_text[:200]
    memory_str = get_relevant_memories(memory_query, user_id="jolie", limit=5)
    
    memory_injection = ""
    if memory_str:
        memory_injection = f"【系统最高指令】：以下是用户设定的核心偏好与历史记忆：\n{memory_str}\n\n"
    
    # 🌟 灵魂：从飞书拉取策略逻辑
    soul_prompt = get_active_prompt_from_feishu(
        keyword="评估", 
        fallback_prompt="你是一位资深业务负责人，请对简历进行严格评估。"
    )
    
    # 🌟 肉体：锁死在后端的 JSON 格式约束（兼容 DashScope：必须明确提及 JSON）
    body_format = """
【输出格式要求（最高优先级）】
必须、严格、仅输出一个纯净的 JSON 对象，不要包含任何 Markdown 代码块标记，也不要包含任何开场白或结束语。
请以 JSON 格式输出，JSON 必须包含且仅包含以下字段：
- "extracted_skills": 字符串数组字符串数组，提取 JD 明确要求的硬技能和工具
- "dream_picture": 字符串。理想画像与能力信号总结
- "ats_ability_analysis": 字符串。ATS词及核心能力词典分析
- "strong_fit_assessment": 字符串。高杠杆匹配点
- "risk_red_flags": 字符串。致命硬伤与后果推演
- "deep_action_plan": 字符串。破局行动计划与关键信息索取
"""
    
    system_prompt = f"{memory_injection}{soul_prompt}\n\n{body_format}"

    try:
        response = get_openai_client().chat.completions.create(
            model=OPENAI_MODEL, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"【岗位描述(JD)】：\n{jd_text}\n\n【我的当前简历】：\n{resume_text}"}
            ],
            temperature=0.1 
        )

        content = response.choices[0].message.content.strip()
        
        # 🌟 安全清理外壳（避开了会导致渲染崩溃的语法）
        prefix_json = "`" * 3 + "json"
        suffix = "`" * 3
        if content.startswith(prefix_json): content = content[7:]
        elif content.startswith(suffix): content = content[3:]
        if content.endswith(suffix): content = content[:-3]
            
        return json.loads(content.strip())
        
    except Exception as e:
        print(f"\n❌ [get_job_match_score] API 调用失败，完整错误详情：")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误内容: {e}")
        import traceback
        traceback.print_exc()
        return {
            "extracted_skills": [], "dream_picture": "API调用失败，请查看终端日志", 
            "ats_ability_analysis": "API调用失败", "strong_fit_assessment": "API调用失败", 
            "risk_red_flags": "API调用失败", "deep_action_plan": "API调用失败"
        }


# ==========================================
# 任务 2：定制化简历改写 (纯 Markdown 输出，无 JSON 约束)
# ==========================================
def rewrite_resume_for_job(resume_text, jd_text, diagnosis_dict, job_name=""):
    diagnosis_str = json.dumps(diagnosis_dict, ensure_ascii=False, indent=2)
    
    memory_query = f"{job_name} {jd_text[:200]}" if job_name else jd_text[:200]
    memory_str = get_relevant_memories(memory_query, user_id="jolie", limit=5)
    
    memory_injection = ""
    if memory_str:
        memory_injection = f"【个人风格与事实依据】：必须严格遵守以下事实和行文风格，切勿编造：\n{memory_str}\n\n"
    
    # 🌟 灵魂：从飞书拉取策略逻辑 (Copilot 灵魂注入)
    soul_prompt = get_active_prompt_from_feishu(
        keyword="改写", 
        fallback_prompt="你是一位资深猎头，请对简历进行针对性改写。"
    )
    
    
    # 🌟 肉体： Markdown 自由生成约束
    body_format = """
你是一位顶级资深猎头，请对简历进行外科手术式改写。
【改写要求】：
- 必须使用标准 Markdown 格式，完全镜像一级标题：必须 100% 保留原始简历中的所有一级标题（# 个人总结、# 专业技能、# 项目经历 等），一级标题（#）代表简历大模块。
- 极致去 AI 化：使用动词+数据+结果，禁止假大空。
- 自动高亮：使用 **双星号** 加粗关键技术栈、核心 KPI 数据和高价值业务动作。
- 列表排版：使用 • 或 - 进行分点描述，支持多级缩进。
"""
    
    system_prompt = f"{memory_injection}{soul_prompt}\n\n{body_format}"

    _empty_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    try:
        response = get_openai_client().chat.completions.create(
            model=OPENAI_MODEL, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"【目标岗位 JD】:\n{jd_text}\n\n【原始简历】:\n{resume_text}\n\n【深度诊断报告】:\n{diagnosis_str}"}
            ],
            temperature=0.4 
        )

        content = response.choices[0].message.content.strip()
        usage = response.usage
        usage_dict = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        } if usage else _empty_usage

        # 🌟 安全清理外壳（剔除代码块标记）
        content = re.sub(r'^```[a-z]*\n?', '', content, flags=re.MULTILINE)
        content = re.sub(r'\n?```$', '', content, flags=re.MULTILINE)
            
        return content.strip(), usage_dict
    except Exception as e:
        print(f"\n❌ [rewrite_resume_for_job] API 调用失败，完整错误详情：")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误内容: {e}")
        import traceback
        traceback.print_exc()
        return "简历定制失败，请检查终端日志查看 API 报错详情。", _empty_usage


# ==========================================
# 任务 3：写打招呼语 (纯文本)
# ==========================================
def generate_greeting(resume_text, jd_text, job_name=""):
    memory_query = f"{job_name} {jd_text[:200]}" if job_name else jd_text[:200]
    memory_str = get_relevant_memories(memory_query, user_id="jolie", limit=5)
    
    memory_injection = ""
    if memory_str:
        memory_injection = f"【个人风格与事实依据】：必须严格遵守以下事实和行文风格：\n{memory_str}\n\n"
    
    # 🌟 灵魂：从飞书拉取策略逻辑
    soul_prompt = get_active_prompt_from_feishu(
        keyword="开场", # 这里根据你的命名习惯抓取，"写开场白" 会命中
        fallback_prompt="你是一位猎头，请帮我写一段针对该岗位的破冰打招呼语。"
    )
    
    # 🌟 肉体：锁死文本约束
    body_format = "【输出格式要求】请直接输出打招呼语的纯文本。绝不能包含任何代码块标记、思考过程、解释性语言或前缀。"
    
    system_prompt = f"{memory_injection}{soul_prompt}\n\n{body_format}"
    
    _empty_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    try:
        response = get_openai_client().chat.completions.create(
            model=OPENAI_MODEL, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"【目标岗位 JD】:\n{jd_text}\n\n【我的个人简历】:\n{resume_text}"}
            ],
            temperature=0.7 
        )
        usage = response.usage
        usage_dict = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        } if usage else _empty_usage
        return response.choices[0].message.content.strip(), usage_dict
    except Exception as e:
        print(f"\n❌ [generate_greeting] API 调用失败，完整错误详情：")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误内容: {e}")
        import traceback
        traceback.print_exc()
        return "您好，我对该岗位非常感兴趣，我的过往经验与岗位需求匹配度较高。在线简历即完整简历，您方便的话可以详细了解下，若看完有意向的话我们做进一步沟通？", _empty_usage


# ==========================================
# 任务 4：第二阶段深度评估（双阶段漏斗架构）
# ==========================================
def deep_evaluate_resume(resume_text: str, jd_text: str, ai_result: dict) -> tuple:
    """
    第二阶段深度评估：接收第一阶段10维度结果作为参考，
    输出完整的画像分析、ATS词分析、风险挖掘等深度报告。
    Returns: (result_dict, usage_dict)
    """
    diagnosis_str = json.dumps(ai_result, ensure_ascii=False, indent=2)

    soul_prompt = get_active_prompt_from_feishu(
        keyword="评估",
        fallback_prompt="你是一位资深猎头与职业规划专家，请基于初步评估结果对候选人与目标岗位进行深度分析。"
    )

    body_format = """
【输出格式要求（最高优先级）】
必须、严格、仅输出一个纯净的 JSON 对象，不含任何 Markdown 代码块标记。
请以 JSON 格式输出，JSON 必须包含且仅包含以下字段：
- "extracted_skills": 字符串数组，提取 JD 明确要求的硬技能和工具
- "dream_picture": 字符串。理想画像与能力信号总结
- "ats_ability_analysis": 字符串。ATS词及核心能力词典分析
- "strong_fit_assessment": 字符串。高杠杆匹配点
- "risk_red_flags": 字符串。致命硬伤与后果推演
- "deep_action_plan": 字符串。破局行动计划与关键信息索取

【极度重要】：必须严格使用上述英文作为 JSON 的 Key。绝对禁止使用中文标题（如"核心能力词典"、"致命硬伤"、"破局行动计划"等）作为 Key，否则系统将崩溃！
"""

    system_prompt = f"{soul_prompt}\n\n{body_format}"
    _empty_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    _fallback = {
        "extracted_skills": [],
        "dream_picture": "深度评估失败",
        "ats_ability_analysis": "深度评估失败",
        "strong_fit_assessment": "深度评估失败",
        "risk_red_flags": "深度评估失败",
        "deep_action_plan": "深度评估失败",
    }

    try:
        response = get_openai_client().chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"【目标岗位 JD】:\n{jd_text}\n\n"
                        f"【候选人简历】:\n{resume_text}\n\n"
                        f"【第一阶段10维度评估结果（参考）】:\n{diagnosis_str}"
                    ),
                },
            ],
            temperature=0.2,
        )
        raw = response.choices[0].message.content.strip()
        usage = response.usage
        usage_dict = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        } if usage else _empty_usage
        _prefix_json = "`" * 3 + "json"
        _suffix = "`" * 3
        if raw.startswith(_prefix_json): raw = raw[7:]
        elif raw.startswith(_suffix): raw = raw[3:]
        if raw.endswith(_suffix): raw = raw[:-3]
        raw = raw.strip()
        return json.loads(raw), usage_dict
    except Exception as e:
        print(f"\n❌ [deep_evaluate_resume] API 调用失败，完整错误详情：")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误内容: {e}")
        import traceback
        traceback.print_exc()
        return _fallback, _empty_usage


# ==========================================
# 工具函数：Markdown 简历解析器
# ==========================================
def parse_resume_markdown(md_text: str) -> List[Dict]:
    """
    将 Markdown 简历文本解析为 Section 列表。
    例：# 个人总结\n内容 → [{"title": "个人总结", "content": "内容"}]
    """
    # 剔除可能存在的代码块外壳（如 ```markdown 、```json 等）
    md_text = re.sub(r'^```[a-z]*\n?', '', md_text, flags=re.MULTILINE)
    md_text = re.sub(r'\n?```$', '', md_text, flags=re.MULTILINE)
    md_text = md_text.strip()

    sections: List[Dict] = []
    current_title: str | None = None
    current_lines: List[str] = []

    for line in md_text.splitlines():
        if line.startswith("# "):
            if current_title is not None:
                sections.append({
                    "title": current_title,
                    "content": "\n".join(current_lines).strip(),
                })
            current_title = line[2:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_title is not None:
        sections.append({
            "title": current_title,
            "content": "\n".join(current_lines).strip(),
        })
    return sections


# ==========================================
# 工具函数：Serper 公司情报搜索
# ==========================================
def search_company_info_serper(company_name: str) -> str:
    """
    调用 Serper.dev 搜索公司融资/规模/产品情报，返回结构化背景文本。
    使用 get_serper_api_key() 动态读取最新 Key，若 Key 为空则优雅降级。
    """
    if not company_name or "某" in company_name or company_name == "未知公司":
        return "⚠️ 匿名或未知公司，跳过外部背调"

    api_key = get_serper_api_key()
    if not api_key:
        return "⚠️ 情报获取失败，降级评估（未配置 SERPER_API_KEY）"

    try:
        url = "https://google.serper.dev/search"
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        payload = {
            "q": f"{company_name} 公司介绍 核心业务 融资",
            "gl": "cn",
            "hl": "zh-cn",
            "num": 5,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        data = resp.json()

        snippets = []
        for item in data.get("organic", [])[:5]:
            snippet = item.get("snippet", "").strip()
            if snippet:
                snippets.append(snippet)

        if not snippets:
            return "⚠️ 情报获取失败，降级评估"

        intel = f"【{company_name} 公司情报】\n" + "\n".join(f"· {s}" for s in snippets[:3])
        return intel[:500]
    except Exception as e:
        print(f"   ❌ [Serper] 请求异常: {type(e).__name__}: {e}")
        return f"⚠️ 情报获取失败，降级评估（{str(e)[:60]})"