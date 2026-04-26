import os
import sys
import time
import json
import argparse
import requests
from openai import OpenAI

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from common.feishu_api import (
    get_pending_apply_jobs, 
    update_job_record,
    get_tenant_access_token,
    extract_feishu_text
)
# 🌟 1. 从配置中心导入大模型配置与飞书表 ID
from common.config import (
    OPENAI_MODEL, 
    FEISHU_APP_TOKEN,
    FEISHU_TABLE_ID_PROMPTS,
    FEISHU_TABLE_ID_RESUMES,
    get_openai_client,
)
# 🌟 2. 导入记忆管理器
from memory_manager import get_relevant_memories

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==========================================
# 🌟 新增：动态从飞书拉取 Prompt 的引擎
# ==========================================
def get_active_prompt_from_feishu(keyword: str, fallback_prompt: str) -> str:
    """
    根据关键字去飞书拉取当前处于【启用】状态的 Prompt
    """
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

# ==========================================
# 🌟 新增：动态从飞书读取云端简历
# ==========================================
def load_resume():
    """
    从飞书配置中心动态读取【启用】状态的简历内容
    """
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
            else:
                print("❌ 启用的简历内容为空！")
                return None
        else:
            print("❌ 未在飞书中找到处于【启用】状态的简历！请前往控制台设置。")
            return None
            
    except Exception as e:
        print(f"❌ 读取云端简历出错: {e}")
        return None

def generate_custom_materials(resume_text, jd_text, job_name=""):
    if len(jd_text) > 1200:
        jd_text = jd_text[:1200] + "...(后略)"

    # 获取相关记忆
    memory_query = f"{job_name} {jd_text[:200]}" if job_name else jd_text[:200]
    memory_str = get_relevant_memories(memory_query, user_id="jolie", limit=5)
    
    # 构建记忆注入部分
    memory_injection = ""
    if memory_str:
        memory_injection = f"【个人风格与事实依据】：在改写简历和生成招呼语时，必须严格遵守以下事实和行文风格，切勿编造违背以下设定的经历：\n{memory_str}\n\n"

    # ==========================
    # 任务 1：打招呼语
    # ==========================
    soul_prompt_greeting = get_active_prompt_from_feishu(
        keyword="开场", 
        fallback_prompt="你是一位拥有10年经验的资深猎头兼高情商求职专家，请帮我写一段针对该岗位的破冰打招呼语。"
    )
    body_format_greeting = "【排版要求】：四段内容之间必须各空一行，总字数控制在 200 字左右。请直接输出打招呼语的纯文本，绝不能包含任何解释或前缀。"
    
    system_prompt_greeting = f"{memory_injection}{soul_prompt_greeting}\n\n{body_format_greeting}"
    user_prompt_greeting = f"【目标岗位 JD】:\n{jd_text}\n\n【原始简历】:\n{resume_text}\n\n附加提示：岗位名称请直接使用【{job_name}】。"

    # ==========================
    # 任务 2：简历定制改写
    # ==========================
    # 🌟 灵魂：从飞书拉取策略逻辑 (Copilot 灵魂注入)
    soul_prompt_resume = get_active_prompt_from_feishu(
        keyword="改写", 
        fallback_prompt="你是一位拥有 15 年经验的顶级求职 Copilot 兼资深猎头专家，专注于帮助候选人深度解析岗位需求并精准重构简历内容。请对候选人简历进行外科手术式的深度重组与改写。"
    )
    
    # 🋡️ 安全阀：清洗掉之前残留在飞书里的 JSON 约束毒素
    if "JSON" in soul_prompt_resume or "json_object" in soul_prompt_resume or "json" in soul_prompt_resume.lower():
        soul_prompt_resume = "你是一位拥有 15 年经验的顶级求职 Copilot 兼资深猎头专家。请对简历进行外科手术式改写，绝对禁止输出 JSON，必须输出标准 Markdown 格式。"
    
    # 🌟 肉体： Copilot 级排版与结构强约束 + 挂载理由与待办清单
    body_format_resume = """
【排版与结构极度严格要求】（最高优先级，绝对不可违反）：
1. **完全镜像一级标题**：必须 100% 读取并保留原始简历中的所有一级标题（例如：# 个人总结、# 专业技能、# 项目经历 等）。原简历有哪几个一级标题、叫什么名字、是什么顺序，你的输出就必须完全一致！绝不可凭空增删、合并或随意更改标题名称。
2. **绝对禁止多级标题**：全文【严禁】使用任何二级标题（##）或三级标题（###）。
3. **内容扁平化排版**：将改写后的内容直接塞入对应的一级标题下方。所有具体的项目名称、公司名称或分类名称，请直接以加粗文本（例如 **公司名称 · 岗位名称 · 周期** 或 **项目名称 · 角色 · 周期**）作为段落开头即可。
4. **列表排版**：使用 • 或 - 进行分点描述，不要使用多级复杂缩进。
5. **纯文本输出**：直接输出 Markdown 纯文本，绝对不要包含 ```markdown 等代码块包裹符号。

【改写基调与专业要求】（Copilot 灵魂）：
1. **精准对标 JD**：深入理解目标岗位 JD 的核心诉求，将关键要素自然、无痕地融入候选人的经历中。
2. **极致去 AI 化与 CAR 结构**：经历描述必须采用 "动词 + 数据 + 结果"（Challenge-Action-Result）结构。保留真实的业务操盘与决策细节，拒绝干瘪短句、假大空词汇和机械式的套话堆砌。
3. **自动高亮**：使用 **双星号** 加粗关键技术栈、核心 KPI 数据和高价值业务动作。

【独家功能：改写理由与待办清单】（必须包含）：
1. **挂载改写理由**：在每一个【项目经历】和【工作经历】的独立描述末尾，必须紧跟一个 Markdown 引用块（> 💡 Copilot 优化思路：...），用极其简练的一句话向候选人解释：为什么这么改？（如：精准对标了 JD 中的 XX 需求，或强化了 XX 商业化操盘能力）。
2. **追加待办清单**：在整份简历输出的最后，必须另起一个一级标题 `# 待办与补充清单`。若你在改写时发现某段经历缺乏关键数据、技术细节或与 JD 强相关的证明，请以列表形式明确指出（例如：建议在XX项目中补充日均处理的SKU量级数据）；若当前信息已完美匹配 JD 且足够详实，则直接输出“当前简历信息已很完善，无需补充”。
改写风格样本学习】：
你的改写必须模仿以下高质量样本：
- 项目经历风格：
  **[项目名称] · [角色] · [时间]**
  **技术栈**：[从原简历提取]
  **业务背景**：针对[痛点]...
  **核心贡献**：使用[CAR结构描述动作与技术落地]
  **量化成果**：[数据百分比]
- 工作经历风格：
  **[公司名] · [岗位] · [时间]**
  - [通过XX技术解决了XX业务痛点，产出了XX结果]
"""
    system_prompt_resume = f"{memory_injection}{soul_prompt_resume}\n\n{body_format_resume}"
    user_prompt_resume = f"【目标岗位 JD】:\n{jd_text}\n\n【原始简历】:\n{resume_text}"

    try:
        print("      🧠 正在构思高情商打招呼语...")
        response_greeting = get_openai_client().chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt_greeting},
                {"role": "user", "content": user_prompt_greeting}
            ],
            temperature=0.7
        )
        greeting = response_greeting.choices[0].message.content.strip()

        print("      📝 正在根据 JD 重新排版定制简历...")
        response_resume = get_openai_client().chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt_resume},
                {"role": "user", "content": user_prompt_resume}
            ],
            temperature=0.5
        )
        custom_resume = response_resume.choices[0].message.content.strip()

        # 🌟 安全清理 JSON 外壳
        prefix_md = "`" * 3 + "markdown"
        prefix_json = "`" * 3 + "json"
        suffix = "`" * 3
        if custom_resume.startswith(prefix_md): custom_resume = custom_resume[11:]
        elif custom_resume.startswith(prefix_json): custom_resume = custom_resume[7:]
        elif custom_resume.startswith(suffix): custom_resume = custom_resume[3:]
        if custom_resume.endswith(suffix): custom_resume = custom_resume[:-3]

        return greeting, custom_resume.strip()

    except Exception as e:
        print(f"      ❌ AI 生成失败: {e}")
        return None, None

def start_assistant():
    print("🎯 启动【AI 狙击手引擎】: 专注文案生成与简历定制...\n")
    
    # 🌟 修改：调用全新的飞书读取函数
    base_resume = load_resume()
    if not base_resume:
        print("❌ 找不到基础简历，任务终止！")
        return

    print("\n📡 正在扫描飞书，寻找状态为【简历AI改写】的目标...")
    target_jobs = get_pending_apply_jobs()
    
    if not target_jobs:
        print("🤷‍♂️ 飞书中目前没有需要生成的【简历AI改写】岗位！")
        return
        
    print(f"✅ 发现 {len(target_jobs)} 个高优待投递岗位！开始逐一击破...\n")

    for i, job in enumerate(target_jobs):
        company_name = job['company']
        job_title = job['job_title']
        print(f"{'='*40}")
        print(f"🎯 [{i+1}/{len(target_jobs)}] 正在处理: {company_name} - {job_title}")
        
        jd_text = job['jd_text']
        if not jd_text or len(jd_text) < 50:
            print("      ⚠️ 详情太短，跳过。")
            continue

        greeting, custom_resume = generate_custom_materials(base_resume, jd_text, job_title)
        
        if greeting and custom_resume:
            print("      ☁️ 正在将打招呼语与 AI 改写 JSON 写回飞书多维表格...")
            is_success = update_job_record(job['record_id'], greeting, custom_resume)
            
            if is_success:
                print("      🚀 写入成功！快去飞书验收吧！")
            else:
                print("      ❌ 写入飞书失败。")
        
        time.sleep(2)
        
    print("\n🏁 所有岗位处理完毕！")

def run_single_job_rewrite(record_id, table_id):
    """
    处理单个岗位的简历改写（由 API 触发）
    """
    print(f"\n{'='*60}")
    print(f"🌟 [单岗位模式] 开始处理 Record ID: {record_id}")
    print(f"{'='*60}")
    
    # 🌟 修改：调用全新的飞书读取函数
    base_resume = load_resume()
    if not base_resume:
        print("❌ 简历加载失败，退出")
        return
    
    try:
        token = get_tenant_access_token()
        if not token:
            print("❌ 飞书鉴权失败")
            return
        
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records/{record_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data.get("code") != 0:
            print(f"❌ 拉取记录失败: {data.get('msg')}")
            return
        
        record = data.get("data", {}).get("record", {})
        fields = record.get("fields", {})
        
        company = fields.get("公司名称", "未知公司")
        job_title = fields.get("岗位名称", "未知岗位")
        jd_text = fields.get("岗位详情", "")
        
        print(f"✅ 成功拉取岗位: {company} - {job_title}")
        
        if not jd_text or len(jd_text) < 50:
            print("⚠️ 岗位详情太短，跳过处理")
            return
        
    except Exception as e:
        print(f"❌ 拉取岗位数据失败: {e}")
        return
    
    print("🤖 正在生成打招呼语与定制简历...")
    greeting, custom_resume = generate_custom_materials(base_resume, jd_text, job_title)
    
    if greeting and custom_resume:
        print("☁️ 正在将打招呼语与 AI 改写 JSON 写回飞书多维表格...")
        is_success = update_job_record(record_id, greeting, custom_resume)
        
        if is_success:
            print("\n✅ 成功处理岗位！打招呼语与定制简历已写入飞书")
        else:
            print("\n❌ 写入飞书失败")
    else:
        print("\n❌ 生成定制材料失败")
    
    print(f"{'='*60}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='简历改写助手')
    parser.add_argument('--record_id', type=str, help='飞书记录 ID')
    parser.add_argument('--table_id', type=str, help='飞书表格 ID')
    
    args = parser.parse_args()
    
    if args.record_id and args.table_id:
        run_single_job_rewrite(args.record_id, args.table_id)
    else:
        start_assistant()