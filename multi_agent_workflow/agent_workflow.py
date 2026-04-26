import os
import sys
import json
import re
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# ==========================================
# 0. 基础环境配置
# ==========================================
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from common.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

# ==========================================
# 1. 定义状态字典 (State) - 专家组的共享记事本
# ==========================================
class ResumeState(TypedDict):
    original_full_text: str               # 原始简历全文
    jd: str                               # 目标岗位JD
    diagnosis_report: str                 # 深度评估报告
    parsed_blocks: List[Dict]             # Agent 1 拆解后的块 (含 mutable/immutable 标签)
    working_rewritten_blocks: List[Dict]  # Agent 2 重写后的块
    critic_feedback: str                  # Agent 3 的审核意见
    current_score: int                    # Agent 3 打出的总分
    revision_count: int                   # 迭代次数
    token_usage: Dict                     # Token 消耗统计
    logs: List[str]                       # 流程日志
    final_markdown: str                   # Agent 4 拼装后的成品

llm = ChatOpenAI(
    model=LLM_MODEL or "gpt-4o",
    temperature=0.3,
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL
)

def _accumulate_tokens(state: ResumeState, response) -> dict:
    prev = state.get("token_usage") or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    meta = getattr(response, "usage_metadata", None) or {}
    return {
        "prompt_tokens": prev["prompt_tokens"] + meta.get("input_tokens", 0),
        "completion_tokens": prev["completion_tokens"] + meta.get("output_tokens", 0),
        "total_tokens": prev["total_tokens"] + meta.get("total_tokens", 0),
    }

def _parse_json_safely(content: str) -> dict:
    content = content.strip()
    pattern = r"```(?:json)?\s*(.*?)\s*```"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    json_str = match.group(1) if match else content

    try:
        return json.loads(json_str)
    except Exception as e:
        print(f"\n⚠️ [JSON解析致命失败] 报错: {e}")
        return {}

# ==========================================
# 2. Agent 节点定义
# ==========================================

# 🟢 Agent 1: 语义拆解大师 (Splitter)
def splitter_agent(state: ResumeState):
    logs = state.get("logs", [])
    logs.append("🟢 [Agent 1-拆解员] 正在进行简历语义切块与安全打标...")
    
    # 🌟 修复点1：JSON 模板中的 {} 必须使用 {{ }} 进行转义
    system_msg = (
        "你是一个高精度的简历语义解析引擎。\n"
        "你的任务是读取原始简历，凭逻辑模块精准拆分为 JSON 数组，并打上安全标签。\n\n"
        "【分类规则】：\n"
        "1. immutable（绝对不可变）：客观静态事实，如“教育背景”、“基本信息”、“个人信息”、“开源项目”、“荣誉证书”等。\n"
        "2. mutable（可深度改写）：需结合业务深度包装的模块，如“个人总结”、“专业技能”、“项目经历”、“工作经历”。\n\n"
        "【切块原则】：\n"
        "必须 100% 毫无遗漏地保留用户的每一个字！切块后的 original_content 组合起来，必须等同于原始简历。\n\n"
        "【输出格式】：\n"
        "必须输出严格的 JSON 格式，不要包含 markdown 代码块标记。格式如下：\n"
        "{{\n"
        "  \"parsed_resume\": [\n"
        "    {{\n"
        "      \"title\": \"模块标题（如：项目经历）\",\n"
        "      \"type\": \"mutable 或 immutable\",\n"
        "      \"original_content\": \"完整原始文本\"\n"
        "    }}\n"
        "  ]\n"
        "}}"
    )

    prompt = ChatPromptTemplate.from_messages([("system", system_msg), ("user", "{content}")])
    chain = prompt | llm.bind(response_format={"type": "json_object"})
    response = chain.invoke({"content": state["original_full_text"]})
    
    data = _parse_json_safely(response.content)
    parsed_blocks = data.get("parsed_resume", [])
    if not parsed_blocks:
        logs.append("🔴 [Agent 1-拆解员] 严重警告：未能成功解析出任何模块！")

    token_usage = _accumulate_tokens(state, response)
    logs.append(f"🟢 [Agent 1-拆解员] 拆解完成，共划分为 {len(parsed_blocks)} 个模块。")
    
    return {"parsed_blocks": parsed_blocks, "logs": logs, "token_usage": token_usage}


# 🔵 Agent 2: 重构主刀医生 (Architect / Rewriter)
def rewriter_agent(state: ResumeState):
    logs = state.get("logs", [])
    mutable_blocks = [b for b in state["parsed_blocks"] if b["type"] == "mutable"]
    
    # 🌟 修复点2：JSON 模板转义
    system_msg = (
        "【系统设定】\n"
        "你现在是一位拥有 10 年经验的资深科技大厂核心业务线负责人 (Hiring Manager)，同时也是一位顶级的简历精修导师。你拿到了针对该候选人的《深度诊断报告》。\n"
        "【强制沟通准则】：重写必须像输出技术架构文档一样保持冷酷、精准、客观。绝对禁止奉承、主观预设或空泛形容词。\n\n"
        "【任务目标】\n"
        "你收到的是允许深度改写的模块。请根据【目标岗位 JD】和【深度诊断报告】进行外科手术式重构，化解“硬伤与毒点”。\n\n"
        "【最高强制红线（Zero Hallucination）】\n"
        "1. 绝对真实底线：严禁捏造候选人不具备的底层技术栈（如 Ubuntu, Grafana, aiohttp, K8s 等）。只能在候选人原有的技术栈（Python, FastAPI, LLM, RPA, Pandas, Next.js 等）基础上，向业务和架构维度升维！\n"
        "2. 核心信息锁定：每段经历的【公司名称】、【项目名称】、【时间段】绝对不允许更改！\n"
        "3. 严禁删减履历：【工作经历】必须全量保留，不可造成时间断层；【项目经历】允许择优挑选重组。\n\n"
        "【核心重构原则与文风（极度重要）】\n"
        "1. 抛弃机械模板：绝对不要在文本中写出“业务背景：”、“核心贡献：”、“量化成果：”这样死板的结构词汇！\n"
        "2. 融合式长难句：经历必须是高度融合的业务长句。采用“• **高阶动作提炼**：具体业务语境/痛点 + 采用的技术栈或策略 + 最终实现的业务价值/量化指标”的格式。\n"
        "3. 动态跨界映射：若候选人是美妆背景，JD 是服装/其他垂类，请通过“多模态、智能体、视觉营销、供应链”等高阶抽象概念进行跨界能力平移，而非生硬照搬。\n\n"
        "【👑 优质改写范例（必须严格模仿此颗粒度、长度和排版语气）】\n"
        "• **多模态内容生成与视觉映射**：设计**高级提示词模板**，实现服装/美妆款式换装图、细节图的自动生成，维护品牌视觉一致性，视觉物料准备时间从**天级缩短至毫秒级**。\n"
        "• **智能体工作流编排**：搭建基于LLM的导购Agent，通过**多轮对话设计**解析用户复杂需求（如行业专有术语），提升意图识别准确率至**90%**，验证了AIGC在垂直行业的落地可行性。\n"
        "• **全链路业务自动化闭环**：集成**多平台数据采集+LLM诊断+RPA**全链路，建立“预警→替代方案推荐”的完整处理流程，将单次执行耗时从**20分钟缩短至30秒**，消除超卖资损风险。\n\n"
        "【输出格式要求】\n"
        "必须输出严格的 JSON 格式：\n"
        "{{\n"
        "  \"rewritten_blocks\": [\n"
        "    {{\n"
        "      \"title\": \"原模块标题\",\n"
        "      \"rewritten_content\": \"重构后的文本内容（严格模仿【优质改写范例】的格式，每条必须是长难句）\",\n"
        "      \"rewrite_rationale\": \"向候选人解释改写理由\",\n"
        "      \"missing_data_requests\": [\"缺失的需候选人补充的数据\"]\n"
        "    }}\n"
        "  ]\n"
        "}}"
    )

    if state.get("critic_feedback"):
        user_msg = (
            f"【上一版被打回！当前质检得分】：{state.get('current_score', 0)}\n"
            f"【质检官严厉驳回意见】：{state['critic_feedback']}\n"
            f"【请务必修正以上错误，重新改写以下模块】：\n{json.dumps(mutable_blocks, ensure_ascii=False)}"
        )
        logs.append(f"🔵 [Agent 2-主刀医生] 收到质检反馈 (得分:{state.get('current_score', 0)})，开始第 {state.get('revision_count', 0) + 1} 次重构...")
    else:
        user_msg = (
            f"【目标岗位 JD】:\n{state['jd']}\n\n"
            f"【深度诊断报告】:\n{state['diagnosis_report']}\n\n"
            f"【需要重构的原始模块】:\n{json.dumps(mutable_blocks, ensure_ascii=False)}"
        )
        logs.append("🔵 [Agent 2-主刀医生] 正在根据《诊断报告》和 JD 切入，重构底层业务逻辑...")

    # 🌟 修复点3：将 user_msg 作为 invoke 的参数传入，防止其中的 JSON 干扰 Prompt 解析
    prompt = ChatPromptTemplate.from_messages([("system", system_msg), ("user", "{user_content}")])
    chain = prompt | llm.bind(response_format={"type": "json_object"})
    response = chain.invoke({"user_content": user_msg})
    
    data = _parse_json_safely(response.content)
    working_rewritten_blocks = data.get("rewritten_blocks", [])

    return {
        "working_rewritten_blocks": working_rewritten_blocks, 
        "logs": logs, 
        "token_usage": _accumulate_tokens(state, response)
    }


# 🔴 Agent 3: 评分质检官 (Scoring QA Critic)
def critic_agent(state: ResumeState):
    logs = state.get("logs", [])
    logs.append("🔴 [Agent 3-质检官] 正在进入 5 维度极度严苛的质量与红线审查...")
    
    original_mutable = [b for b in state["parsed_blocks"] if b["type"] == "mutable"]
    
    # 🌟 修复点4：JSON 模板转义
    system_msg = (
        "你是一个极其冷酷、严苛的真假审查员兼质量控制官 (QA)。你的眼里容不得半点虚假、敷衍和时间断层。\n"
        "请对比【原始简历片段】、【当前改写草稿】和【深度诊断报告】，进行 5 维度打分（每项满分 20 分，总分 100 分）：\n\n"
        "1. JD 对齐度 (20分)：是否将 JD 要求的关键词自然融入？有没有强行吹嘘候选人不具备的技能？（若强行扯上关系降维打击，扣 20 分）。\n"
        "2. 业务深度与文风 (20分)：这是重点！草稿是否严格模仿了长难句范例？如果发现描述中带有极其机械的“业务背景：”、“核心贡献：”字样，或者存在低于30字的干瘪短句，或者编造了原简历完全没有的底层服务器技术（如Grafana, aiohttp），重扣 20 分！\n"
        "3. 真实性红线 (20分)：这是生死线！是否篡改了工作/项目的时间段、公司名称？是否擅自删减了【工作经历】导致履历断层？【注意：若触犯此红线，此项直接得 0 分，并在 feedback 中严厉斥责】\n"
        "4. 量化成果 (20分)：是否有具体的数据支撑，且没有凭空捏造极度夸张的数据（如造假 10000 QPS）？若造假，扣 20 分。\n"
        "5. 格式专业度 (20分)：是否使用了 `• **小标题**：长句正文` 的排版格式？有无假大空词汇？\n\n"
        "【输出格式】：必须输出严格的 JSON 格式：\n"
        "{{\n"
        "  \"score\": 整数总分,\n"
        "  \"reasoning\": \"简述各项扣分或得分原因\",\n"
        "  \"feedback\": \"具体的改进建议和强制修改指令（若无扣分填无）\"\n"
        "}}"
    )

    user_msg = (
        f"【原始简历可变模块】：{json.dumps(original_mutable, ensure_ascii=False)}\n\n"
        f"【当前主刀医生改写草稿】：{json.dumps(state['working_rewritten_blocks'], ensure_ascii=False)}\n\n"
        f"【深度诊断报告】：{state['diagnosis_report']}"
    )
    
    prompt = ChatPromptTemplate.from_messages([("system", system_msg), ("user", "{user_content}")])
    chain = prompt | llm.bind(response_format={"type": "json_object"})
    response = chain.invoke({"user_content": user_msg})
    
    res_data = _parse_json_safely(response.content)
    if res_data:
        score = int(res_data.get("score", 0))
        reasoning = res_data.get("reasoning", "")
        feedback = res_data.get("feedback", "")
    else:
        score, reasoning, feedback = 0, "解析打分失败", "JSON解析错误"

    new_count = state.get("revision_count", 0) + 1
    
    if score >= 80:
        logs.append(f"🔴 [Agent 3-质检官] 评审通过！总得分：{score} 分。评语：{reasoning[:50]}...")
    else:
        logs.append(f"🔴 [Agent 3-质检官] ⚠️ 发现严重质量/红线问题！得分：{score} 分。打回原因：{feedback[:80]}...")
        
    return {
        "current_score": score,
        "critic_feedback": feedback,
        "revision_count": new_count,
        "logs": logs,
        "token_usage": _accumulate_tokens(state, response)
    }


# 🟣 Agent 4: 拼图排版大师 (Merger & Formatter)
def formatter_agent(state: ResumeState):
    logs = state.get("logs", [])
    logs.append("🟣 [Agent 4-排版大师] 正在执行无损拼图还原与 Markdown 语法强控...")

    rewritten_map = {b["title"]: b.get("rewritten_content", "") for b in state["working_rewritten_blocks"]}
    
    merged_data = []
    for block in state["parsed_blocks"]:
        if block["type"] == "immutable":
            merged_data.append({"title": block["title"], "content": block["original_content"]})
        else:
            merged_data.append({"title": block["title"], "content": rewritten_map.get(block["title"], block["original_content"])})

    system_msg = (
        "你是一位顶级资深猎头，负责最终简历的视觉呈现与结构拼接。\n"
        "你现在只是一个精准的 Markdown 格式转换器与拼图机器人，绝对禁止总结、精简或删减任何文字！\n\n"
        "【拼装与排版强制要求】（违规即判定失败）：\n"
        "1. 完整拼接：将提供的数据按原顺序组合，绝对不能遗漏任何一句话！\n"
        "2. 纯粹的一级标题：所有模块的名称必须且只能使用一级标题（`# `），绝对禁止使用二级（`## `）或三级（`### `）标题！\n"
        "3. 魔法分割线（极其重要）：在每一个一级标题（`# `）的正下方，必须且只能紧跟单独的一行 `****`，然后在下一行才开始写正文内容。\n"
        "4. 经历副标题定式：所有【项目经历】和【工作经历】的副标题行，必须严格取消 Markdown 标题语法（不用 #），直接使用双星号加粗，并以间隔号（·）分隔结构，格式必须如下：\n"
        "   `**项目/公司名称 · 岗位Title · 时间段**`\n"
        "5. 列表与高亮：正文使用 `- ` 进行分点描述，必须使用 **双星号** 加粗关键技术栈、核心业务动作和 KPI 数据。\n\n"
        "【输出要求】直接输出拼接与排版后的最终 Markdown 纯文本内容，不要包含 ```markdown 等代码块标记。"
    )

    user_msg = f"【需要组装的完整模块数据】：\n{json.dumps(merged_data, ensure_ascii=False)}"

    # 🌟 修复点5：参数隔离传递
    prompt = ChatPromptTemplate.from_messages([("system", system_msg), ("user", "{user_content}")])
    chain = prompt | llm
    response = chain.invoke({"user_content": user_msg})
    
    token_usage = _accumulate_tokens(state, response)
    logs.append(f"📊 [Token 终极结账] 全流程消耗 -> prompt: {token_usage['prompt_tokens']}, completion: {token_usage['completion_tokens']}, total: {token_usage['total_tokens']}")
    
    return {
        "final_markdown": response.content.strip(),
        "logs": logs,
        "token_usage": token_usage
    }

# ==========================================
# 3. 路由器函数 (80分放行机制)
# ==========================================
def review_router(state: ResumeState):
    score = state.get("current_score", 0)
    count = state.get("revision_count", 0)
    
    if score >= 80:
        state["logs"].append(f"✅ [判定] 质检分 {score} >= 80，完美表现，进入装订阶段。")
        return "approved"
    
    if count < 2:
        state["logs"].append(f"⚠️ [判定] 质检分 {score} 未达标，触发强制打回修正(第1次)...")
        return "rejected"
    
    state["logs"].append(f"⌛ [判定] 已完成打回修正(当前分:{score})，为避免死循环，强行进入装订阶段。")
    return "approved"

# ==========================================
# 4. 组装多 Agent 循环图
# ==========================================
workflow = StateGraph(ResumeState)

workflow.add_node("Splitter", splitter_agent)
workflow.add_node("Architect", rewriter_agent)
workflow.add_node("Critic", critic_agent)
workflow.add_node("Formatter", formatter_agent)

workflow.set_entry_point("Splitter")
workflow.add_edge("Splitter", "Architect")
workflow.add_edge("Architect", "Critic")

workflow.add_conditional_edges(
    "Critic",
    review_router,
    {
        "rejected": "Architect",
        "approved": "Formatter"
    }
)

workflow.add_edge("Formatter", END)

multi_agent_app = workflow.compile()