#!/usr/bin/env python3
"""
QA Evaluator - 简历二次质检模块
对 AI 改写后的简历进行最终质量保证检查
"""

import json
import requests
from openai import OpenAI
from common.config import (
    OPENAI_API_KEY, 
    OPENAI_BASE_URL, 
    OPENAI_MODEL,
    FEISHU_APP_TOKEN,
    FEISHU_TABLE_ID_PROMPTS
)
from common.feishu_api import get_tenant_access_token, extract_feishu_text

# 🌟 初始化客户端
client = OpenAI(
    api_key=OPENAI_API_KEY, 
    base_url=OPENAI_BASE_URL
)

# ==========================================
# 🌟 新增：动态从飞书拉取 Prompt 的引擎
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

def qa_evaluate_resume(job_description: str, rewritten_resume_text: str) -> dict:
    """对改写后的简历进行二次质检评估"""
    
    # 🌟 灵魂：从飞书拉取 QA 质检策略
    soul_prompt = get_active_prompt_from_feishu(
        keyword="质检", # 建议你在飞书新建一个叫“QA质检”的Prompt记录
        fallback_prompt="你是一个严格的简历质量保证（QA）专家。任务是对AI重写过的简历进行交叉质检。保持冷酷、精准、客观。"
    )

    # 🌟 肉体：锁死强约束 JSON，绝不妥协
    body_format = """
【任务要求】
请快速扫描当前简历，并输出一份极其精简的【最终质检与人工待办报告】。
必须严格输出纯 JSON 字符串，绝不能包含 Markdown 代码块标记。

{
  "match_verification": {
    "achieved_points": [
      "• 列出 2-3 个简历现在已经完美契合 JD 的硬核技能或业务要求"
    ],
    "missing_points": [
      "• 一针见血地指出改写后依然没有体现，或者体现得很弱的 1-2 个 JD 强制要求"
    ]
  },
  "hallucination_check": [
    "• 指出简历中听起来过于宏大或经不起深挖的表述及后果。若无，输出'未发现明显过度包装'"
  ],
  "human_action_items": [
    "[ ] 待办1：请在 XX 项目的成果部分，补充具体的 % 数据",
    "[ ] 待办2：检查技能清单中的 XX 工具，确认是否能够应对白板编程"
  ]
}
"""

    full_prompt = f"{soul_prompt}\n\n{body_format}\n\n【目标岗位 JD】：\n{job_description}\n\n【当前改写后的简历文本】：\n{rewritten_resume_text}"

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content.strip()
        
        # 🌟 安全清理 JSON 外壳（防崩溃语法）
        prefix_json = "`" * 3 + "json"
        suffix = "`" * 3
        if content.startswith(prefix_json): content = content[7:]
        elif content.startswith(suffix): content = content[3:]
        if content.endswith(suffix): content = content[:-3]
        
        qa_report = json.loads(content.strip())
        return qa_report
        
    except json.JSONDecodeError as e:
        error_msg = f"QA 评估 JSON 解析失败: {str(e)}"
        print(f"❌ {error_msg}")
        raise ValueError(error_msg) from e
    except Exception as e:
        error_msg = f"QA 评估 LLM 调用失败: {str(e)}"
        print(f"❌ {error_msg}")
        raise RuntimeError(error_msg) from e


if __name__ == "__main__":
    # 测试代码
    test_jd = "招聘 AI 产品经理，要求熟悉大模型应用开发，有 Prompt Engineering 经验"
    test_resume = "我是一名 AI 产品经理，精通大模型应用开发和 Prompt Engineering"
    
    result = qa_evaluate_resume(test_jd, test_resume)
    print(json.dumps(result, ensure_ascii=False, indent=2))