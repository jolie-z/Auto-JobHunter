#!/usr/bin/env python3
"""
AI 评估引擎 - 独立的岗位智能评估模块

功能：
1. 从飞书拉取所有"新线索"状态的岗位
2. 使用大模型进行深度评估（打分、画像分析、匹配度等）
3. 根据评分自动分流：
   - AI总分 >= 90: 生成简历改写 + 打招呼语，状态设为"待人工复核"
   - AI总分 < 90: 仅保存评估结果，状态设为"待人工评估"
4. 将评估结果回写到飞书多维表格总表
"""

import os
import sys
import json
import time
import random
import argparse
import requests # 🌟 新增 requests 用于拉取云端简历
# 🌟 引入 Python 结构化粗筛引擎（双保险）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'job_processor'))
from structural_filter import StructuralFilterEngine
from openai import OpenAI
# 🌟 引入外部搜索函数
# 🌟 引入外部搜索函数
from ai_scorer import rewrite_resume_for_job, generate_greeting, deep_evaluate_resume, search_company_info_serper
from common.feishu_api import (
    get_new_leads_from_feishu,
    update_feishu_record,
    normalize_ai_rewrite_json_payload,
    extract_rationales_from_json,
    get_tenant_access_token,
    extract_feishu_text,
)
# 🌟 修改 1：引入简历表的 ID 和大模型配置
from common.config import (
    FEISHU_APP_TOKEN,
    FEISHU_TABLE_ID_JOBS,
    FEISHU_TABLE_ID_RESUMES,
    OPENAI_MODEL,
    get_openai_client,
)

# 🌟 初始化结构化粗筛引擎（调用大模型前的双保险拦截）
_filter_engine = StructuralFilterEngine()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 🌟 修改 2：彻底重构简历读取逻辑，废弃本地 txt，拥抱飞书云端
def load_resume():
    """
    从飞书配置中心动态读取【启用】状态的简历内容
    
    Returns:
        str: 简历文本内容，失败返回 None
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

# 10维度 A-F 评估提示词（后端锁死格式约束）
_DIM_LABELS = [
    ("role_match",     "角色匹配"),
    ("skills_align",   "技能重合"),
    ("seniority",      "职级资历"),
    ("compensation",   "薪资契合"),
    ("interview_prob", "面试概率"),
    ("work_mode",      "工作模式"),
    ("company_stage",  "公司阶段"),
    ("market_fit",     "赛道前景"),
    ("growth",         "成长空间"),
    ("timeline",       "招聘周期"),
]


def _format_rationales_text(scores: dict, rationales: dict) -> str:
    """将10维度打分依据格式化为结构化 Markdown 长文本"""
    lines = []
    for key, label in _DIM_LABELS:
        score = scores.get(key, "?")
        reason = rationales.get(key, "")
        if reason:
            lines.append(f"**【{label}】** {score}/5\n{reason}")
    return "\n\n".join(lines)


_EVAL_FORMAT = """
【输出格式要求（最高优先级）】
必须、严格、仅输出一个纯净的 JSON 对象，不含任何 Markdown 代码块标记。
JSON 必须包含且仅包含以下字段：

- "grade": 字符串，综合评级，必须是 A/B/C/D/F 之一（A=顶级匹配，B=良好，C=一般，D=较差，F=完全不匹配）
  ⚠️【一票否决规则（严格执行）】：grade 判定为 F，当且仅当 JD 中出现与候选人偏好中【绝对红线】明确匹配的词句（例如：外包、劳务派遣、单休、应届、仅限专科、特定不接受行业等）。
  🚫 严禁基于猜测（如"可能高压"、"可能需要加班"、"竞争激烈"等推断）判定 F 或 D。信息不足时按中性处理，不得主动扣分。

- "scores": JSON 对象，包含以下 10 个键，每个值为 1-5 的整数：
    【评分校准基准】3分=信息缺失或中性；4分=JD 中有明确正面证据；5分=远超预期且高度契合候选人目标，极为罕见
    "role_match"（核心：角色与目标岗位匹配程度），
    "skills_align"（核心：技能重合度），
    "seniority"（高权：职级资历匹配），
    "compensation"（高权：薪资期望契合度），
    "interview_prob"（高权：面试通过概率），
    "work_mode"（工作模式契合，如远程/驻场），
    "company_stage"（公司发展阶段契合度），
    "market_fit"（中权：赛道市场前景），
    "growth"（中权：个人成长空间），
    "timeline"（招聘紧迫度与周期）

  ⚠️【薪资与城市强制读取规则 - 必须执行】：传入文本包含【岗位基本信息】和【岗位详情】两个区块。在评估 "compensation" 和 "work_mode" 等维度时，必须优先读取【岗位基本信息】中明确标出的薪资范围（如 15-25k）和城市，绝对禁止回答"未披露"或"未说明"！若【岗位基本信息】已有薪资数据，则 compensation 必须基于该数据打分，不得给出中性 3 分。

  ⚠️【外部情报强制读取规则 - 必须执行】：在评估 "company_stage"（公司阶段）和 "market_fit"（赛道前景）时，必须优先参考【公司外部情报（来自网络搜索）】给出的融资历程、规模、主营业务等数据作为打分依据。

  ⚠️【中性维度强制规则 - 必须执行】："work_mode"、"company_stage"、"timeline" 三个维度采用【中性/奖励】逻辑：
    - 默认给 3 分，除非 JD 中有明确正面证据（如"支持远程办公"、"急招"、"A 轮融资后高速增长期"等）才可给 4-5 分。
    - 绝对禁止给出 1-2 分。若信息缺失或无法判断，必须给 3 分，严禁基于猜测扣分。

- "score_rationales": JSON 对象，与 scores 包含相同的 10 个键，每个值为该维度的打分依据（严格限 1 句话，必须直接引用 JD 或简历中的具体信息作为证据，严禁废话和主观猜测）
"""

# 加权评分配置：高相关维度权重高，中性/环境维度权重低
_WEIGHTS = {
    "role_match":     1.0,
    "skills_align":   1.0,
    "seniority":      1.0,
    "interview_prob": 1.0,
    "compensation":   0.8,
    "growth":         0.8,
    "market_fit":     0.8,
    "work_mode":      0.2,
    "company_stage":  0.2,
    "timeline":       0.2,
}

# 采用「中性/奖励」逻辑的三个维度（信息缺失时默认 3 分，不扣分）
_NEUTRAL_DIMS = ("work_mode", "company_stage", "timeline")


def _call_10dim_evaluation(resume_text: str, jd_text: str, company_intel: str = "", preferences_text: str = "") -> dict:
    """直接调用大模型，返回 10 维度 A-F 评估结果 dict，支持注入公司情报与个人偏好"""
    soul_prompt = "你是一名顶级猎头与职业规划专家，请对候选人与目标岗位的匹配度进行专家级深度评估。"
    system_prompt = f"{soul_prompt}\n\n{_EVAL_FORMAT}"

    parts = [f"【目标岗位 JD】\n{jd_text}"]
    if company_intel and not company_intel.startswith("⚠️"):
        parts.append(f"【公司外部情报（来自网络搜索）】\n{company_intel}")
    if preferences_text:
        parts.append(f"【候选人求职偏好与绝对底线】\n{preferences_text}")
    parts.append(f"【候选人简历】\n{resume_text}")
    user_prompt = "\n\n".join(parts)

    _SCORE_KEYS = ["role_match","skills_align","seniority","compensation",
                   "interview_prob","work_mode","company_stage","market_fit","growth","timeline"]
    _empty_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    try:
        response = get_openai_client().chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        raw = (response.choices[0].message.content or "").strip()
        usage = response.usage
        usage_dict = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        } if usage else _empty_usage
        _prefix_json = "```json"
        _suffix = "```"
        if raw.startswith(_prefix_json):
            raw = raw[7:]
        elif raw.startswith(_suffix):
            raw = raw[3:]
        if raw.endswith(_suffix):
            raw = raw[:-3]
        raw = raw.strip()
        try:
            return json.loads(raw), usage_dict
        except json.JSONDecodeError:
            print(f"⚠️ 10维评估解析失败，原始文本:\n{raw}")
            return {
                "grade": "F",
                "scores": {k: 1 for k in _SCORE_KEYS},
                "score_rationales": {k: "AI解析失败" for k in _SCORE_KEYS},
            }, usage_dict
    except Exception as e:
        print(f"\n❌ [_call_10dim_evaluation] API 调用失败，完整错误详情：")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误内容: {e}")
        import traceback
        traceback.print_exc()
        return {
            "grade": "F",
            "scores": {k: 1 for k in _SCORE_KEYS},
            "score_rationales": {k: "AI解析失败" for k in _SCORE_KEYS},
        }, _empty_usage


def evaluate_single_job(job_data, resume_text, company_intel: str = "", preferences_text: str = ""):
    """
    评估单个岗位（10维度 A-F 架构），支持注入公司情报与个人偏好底线
    """
    record_id = job_data.get("record_id")
    company = job_data.get("company", "未知公司")
    job_title = job_data.get("job_title", "未知岗位")
    platform = job_data.get("platform", "未知渠道")
    jd_text = job_data.get("jd_text", "")
    salary = job_data.get("salary", "未知")
    city = job_data.get("city", "未知")
    experience = job_data.get("experience", "未知")
    education = job_data.get("education", "未知")

    # 组装全景 JD 上下文（让 LLM 看到所有基础字段）
    full_jd_info = (
        f"【岗位基本信息】\n"
        f"薪资范围: {salary} | 工作城市: {city} | 经验要求: {experience} | 学历要求: {education}\n\n"
        f"【岗位详情】\n{jd_text}"
    )

    print(f"\n{'='*60}")
    print(f"📋 正在评估: [{platform}] {company} - {job_title}")
    print(f"🆔 Record ID: {record_id}")
    print(f"💰 薪资: {salary} | 📍 城市: {city} | 📚 学历: {education} | 🏷️ 经验: {experience}")

    try:
        # 步骤 0: Python 结构化粗筛（双保险拦截，避免浪费 LLM 调用）
        is_garbage, reason = _filter_engine.is_obvious_garbage(
            job_title=job_title, experience_req=experience, education_req=education
        )
        if is_garbage:
            print(f"   🛑 [Python粗筛拦截] 命中规则: {reason}")
            return {
                "success": True,
                "record_id": record_id,
                "update_data": {
                    "跟进状态": "清洗淘汰",
                    "综合评级 (A-F)": "F",
                    "核心-角色匹配": 0,
                    "核心-技能重合": 0,
                    "高权-职级资历": 0,
                    "高权-薪资契合": 0,
                    "高权-面试概率": 0,
                    "中权-工作模式": 0,
                    "中权-公司阶段": 0,
                    "中权-赛道前景": 0,
                    "中权-成长空间": 0,
                    "低权-招聘周期": 0,
                },
                "ai_score": 0,
                "grade": "F",
                "status": "清洗淘汰",
            }

        # 步骤 1: 10维度大模型评估（注入公司情报 + 个人偏好）
        intel_label = "有情报" if company_intel and not company_intel.startswith("⚠️") else "无情报"
        pref_label = "有偏好" if preferences_text else "无偏好"
        print(f"   🧠 [1/4] 正在呼叫 AI 进行 10维度深度评估... [{intel_label} | {pref_label}]")
        ai_result, eval_usage = _call_10dim_evaluation(resume_text, full_jd_info, company_intel, preferences_text)

        # 初始化 Token 累计器
        total_usage = {
            "prompt_tokens": eval_usage.get("prompt_tokens", 0),
            "completion_tokens": eval_usage.get("completion_tokens", 0),
            "total_tokens": eval_usage.get("total_tokens", 0),
        }

        grade = ai_result.get("grade", "F")
        scores = ai_result.get("scores", {})
        rationales = ai_result.get("score_rationales", {})
        try:
            rationales_text = _format_rationales_text(scores, rationales)
        except Exception:
            rationales_text = ""

        # 强制纠偏：中性维度不得低于 3（仅加分不扣分策略）
        _clamped_count = 0
        for k in _NEUTRAL_DIMS:
            if int(scores.get(k, 3)) < 3:
                scores[k] = 3
                _clamped_count += 1
        if _clamped_count:
            print(f"   🔧 [纠偏] {_clamped_count} 个中性维度低于3分，已强制修正为3分")

        # 加权总分计算
        weighted_sum = sum(int(scores.get(k, 1)) * _WEIGHTS[k] for k in _WEIGHTS)
        max_weighted = sum(5 * _WEIGHTS[k] for k in _WEIGHTS)
        raw_total = sum(int(scores.get(k, 1)) for k in _WEIGHTS)
        ai_total = int(weighted_sum / max_weighted * 100)
        raw_pct = int(raw_total / 50 * 100)
        print(f"   📊 [2/3] 第一阶段诊断完毕！评级: {grade}，加权总分: {ai_total}分（等权参考: {raw_pct}分）")

        # ── 第一阶段 update_data：仅写入 12 个已确认的安全字段 ──
        target_status = ""
        update_data = {
            "综合评级 (A-F)": grade,
            "AI评估详情": rationales_text,
            "核心-角色匹配": int(scores.get("role_match", 0)),
            "核心-技能重合": int(scores.get("skills_align", 0)),
            "高权-职级资历": int(scores.get("seniority", 0)),
            "高权-薪资契合": int(scores.get("compensation", 0)),
            "高权-面试概率": int(scores.get("interview_prob", 0)),
            "中权-工作模式": int(scores.get("work_mode", 0)),
            "中权-公司阶段": int(scores.get("company_stage", 0)),
            "中权-赛道前景": int(scores.get("market_fit", 0)),
            "中权-成长空间": int(scores.get("growth", 0)),
            "低权-招聘周期": int(scores.get("timeline", 0)),
            "跟进状态": "已完成初步评估",  # 占位，高分轨会覆盖
        }

        # ── 步骤 2: 高分轨/低分轨分流 ──
        if grade == "A" or int(ai_total) >= 90:
            print(f"   🔥 [3/3] 触发【高分轨】(A级或>=90分)！正在自动进行深度评估与简历定制...")

            deep_result, deep_usage = deep_evaluate_resume(resume_text, full_jd_info, ai_result)
            total_usage["prompt_tokens"] += deep_usage.get("prompt_tokens", 0)
            total_usage["completion_tokens"] += deep_usage.get("completion_tokens", 0)
            total_usage["total_tokens"] += deep_usage.get("total_tokens", 0)

            extracted_skills = deep_result.get("extracted_skills", [])
            skills_str = "、".join(extracted_skills) if extracted_skills else ""
            ats_base = deep_result.get("ats_ability_analysis", "")
            ats_final = f"{ats_base}\n\n【提取技能词】：{skills_str}" if skills_str else ats_base

            update_data["理想画像与能力信号"] = deep_result.get("dream_picture", "")
            update_data["核心能力词典"] = ats_final
            update_data["高杠杆匹配点"] = deep_result.get("strong_fit_assessment", "")
            update_data["致命硬伤与毒点"] = deep_result.get("risk_red_flags", "")
            update_data["破局行动计划"] = deep_result.get("deep_action_plan", "")

            rewrite_result, rewrite_usage = rewrite_resume_for_job(resume_text, full_jd_info, deep_result, job_name=job_title)
            total_usage["prompt_tokens"] += rewrite_usage.get("prompt_tokens", 0)
            total_usage["completion_tokens"] += rewrite_usage.get("completion_tokens", 0)
            total_usage["total_tokens"] += rewrite_usage.get("total_tokens", 0)
            update_data["AI改写JSON"] = rewrite_result

            greeting_result, greeting_usage = generate_greeting(resume_text, full_jd_info, job_name=job_title)
            total_usage["prompt_tokens"] += greeting_usage.get("prompt_tokens", 0)
            total_usage["completion_tokens"] += greeting_usage.get("completion_tokens", 0)
            total_usage["total_tokens"] += greeting_usage.get("total_tokens", 0)
            update_data["打招呼语"] = greeting_result

            update_data["跟进状态"] = "简历人工复核"
            target_status = "简历人工复核"
        else:
            print(f"   ⏸️ [3/3] 触发【低分轨】({grade}级，{ai_total}分)，跳过深度评估")
            update_data["跟进状态"] = "已完成初步评估"
            target_status = "已完成初步评估"

        print(f"   📈 Token 消耗 → 提示: {total_usage['prompt_tokens']} / 补全: {total_usage['completion_tokens']} / 总计: {total_usage['total_tokens']}")
        return {
            "success": True,
            "record_id": record_id,
            "update_data": update_data,
            "ai_score": ai_total,
            "grade": grade,
            "status": target_status,
            "usage": total_usage,
            "rationales_text": rationales_text,
        }

    except Exception as e:
        print(f"   ❌ 评估过程出错: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "record_id": record_id,
            "error": str(e)
        }

def run_batch_evaluation():
    """批量评估主控函数"""
    print("🚀 启动 AI 评估引擎...\n")
    
    resume_text = load_resume()
    if not resume_text:
        print("❌ 无法读取云端简历，评估任务终止")
        return
    
    print("\n📡 正在从飞书总表拉取【新线索】状态的岗位...")
    print("="*60)
    new_leads = get_new_leads_from_feishu()
    print("="*60)
    
    if not new_leads:
        print("✅ 没有待评估的新线索岗位，任务完成！")
        return
    
    print(f"✅ 成功拉取 {len(new_leads)} 个待评估岗位\n")
    print("="*60)
    
    success_count = 0
    fail_count = 0
    high_score_count = 0
    low_score_count = 0
    
    for idx, job_data in enumerate(new_leads):
        print(f"\n进度: [{idx+1}/{len(new_leads)}]")
        
        # 🚀 新增：在调用评估前，先调用外部 API 抓取情报
        company_name = job_data.get("company", "")
        company_intel = ""
        if company_name and company_name != "未知公司":
            print(f"📡 正在抓取公司外部情报: {company_name}...")
            company_intel = search_company_info_serper(company_name)
            
        # 🚀 修改：把抓到的情报当做参数传进去
        result = evaluate_single_job(job_data, resume_text, company_intel=company_intel)
        
        if result["success"]:
            print(f"   📤 正在将评估结果回写到飞书...")
            is_updated = update_feishu_record(
                result["record_id"],
                result["update_data"]
            )
            
            if is_updated:
                print(f"   ✅ 成功更新飞书记录！状态: {result['status']}, 得分: {result['ai_score']}")
                success_count += 1
                if result["ai_score"] >= 90:
                    high_score_count += 1
                else:
                    low_score_count += 1
            else:
                print(f"   ❌ 飞书回写失败")
                fail_count += 1
        else:
            print(f"   ❌ 评估失败: {result.get('error', '未知错误')}")
            fail_count += 1
        
        if idx < len(new_leads) - 1:
            sleep_time = random.randint(3, 8)
            print(f"   ⏳ 等待 {sleep_time} 秒后处理下一个岗位...")
            time.sleep(sleep_time)
    
    print("\n" + "="*60)
    print("🏁 批量评估任务完成！")
    print("="*60)
    print(f"📊 评估统计:")
    print(f"   - 总计岗位: {len(new_leads)}")
    print(f"   - 成功评估: {success_count}")
    print(f"   - 失败跳过: {fail_count}")
    print(f"   - 高分岗位 (>=90分): {high_score_count} → 状态: 简历人工复核")
    print(f"   - 低分岗位 (<90分): {low_score_count} → 状态: 待人工评估")
    print("="*60)

def run_single_job_evaluation(record_id, table_id=None):
    """处理单个岗位的评估"""
    print(f"\n{'='*60}")
    print(f"🌟 [单岗位模式] 开始处理 Record ID: {record_id}")
    print(f"{'='*60}")
    
    resume_text = load_resume()
    if not resume_text:
        return
    
    try:
        token = get_tenant_access_token()
        if not token:
            print("❌ 飞书鉴权失败")
            return
        
        import requests
        target_table_id = FEISHU_TABLE_ID_JOBS
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{target_table_id}/records/{record_id}"
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
        
        job_data = {
            "record_id": record_id,
            "company": extract_feishu_text(fields.get("公司名称", "")) or "未知公司",
            "job_title": extract_feishu_text(fields.get("岗位名称", "")) or "未知岗位",
            "jd_text": extract_feishu_text(fields.get("岗位详情", "")),
            "salary": extract_feishu_text(fields.get("薪资", "")) or "未知",
            "city": extract_feishu_text(fields.get("城市", "")) or "未知",
            "experience": extract_feishu_text(fields.get("经验要求", "")) or "未知",
            "education": extract_feishu_text(fields.get("学历要求", "")) or "未知",
        }
        
        print(f"✅ 成功拉取岗位: {job_data['company']} - {job_data['job_title']}")
        
    except Exception as e:
        print(f"❌ 拉取岗位数据失败: {e}")
        return
    
    # 🚀 新增：在调用评估前，先调用外部 API 抓取情报
    company_name = job_data.get("company", "")
    company_intel = ""
    if company_name and company_name != "未知公司":
        print(f"📡 正在抓取公司外部情报: {company_name}...")
        company_intel = search_company_info_serper(company_name)
    
    # 🚀 修改：把抓到的情报当做参数传进去
    result = evaluate_single_job(job_data, resume_text, company_intel=company_intel)
    
    if result.get("success"):
        is_updated = update_feishu_record(
            record_id,
            result["update_data"]
        )
        
        if is_updated:
            print(f"\n✅ 成功处理岗位！状态: {result['status']}, 得分: {result['ai_score']}")
        else:
            print(f"\n❌ 飞书回写失败")
    else:
        print(f"\n❌ 评估失败: {result.get('error', '未知错误')}")
    
    print(f"{'='*60}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='AI 岗位评估引擎')
    parser.add_argument('--record_id', type=str, help='飞书记录 ID')
    parser.add_argument('--table_id', type=str, help='(已废弃) 飞书表格 ID，为兼容保留')
    
    args = parser.parse_args()
    
    if args.record_id:
        run_single_job_evaluation(args.record_id)
    else:
        run_batch_evaluation()