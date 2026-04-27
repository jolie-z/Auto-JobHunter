import re
import requests
import json
import time
import urllib3
from datetime import datetime
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# 🌟 修改 1：去掉了废弃的独立表 ID，只保留总表
from config import (
    FEISHU_APP_ID as APP_ID,
    FEISHU_APP_SECRET as APP_SECRET,
    FEISHU_APP_TOKEN as APP_TOKEN,
    FEISHU_TABLE_ID_JOBS as TABLE_ID_JOBS,
    FEISHU_TABLE_ID_CONFIG as TABLE_ID_CONFIG
)

# 🌟 新增：全局 Token 缓存池
_TOKEN_CACHE = {"token": None, "expires_at": 0}

def get_tenant_access_token():
    global _TOKEN_CACHE
    current_time = time.time()
    
    # 🌟 核心：如果缓存的 token 还在有效期内（飞书默认有效期2小时，我们提前5分钟刷新），直接秒回！
    if _TOKEN_CACHE["token"] and current_time < _TOKEN_CACHE["expires_at"] - 300:
        return _TOKEN_CACHE["token"]

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    req_body = {"app_id": APP_ID, "app_secret": APP_SECRET}
    response = requests.post(url, json=req_body, timeout=15, proxies={"http": None, "https": None}, verify=False)
    data = response.json()
    
    if data.get("code") == 0:
        # 存入缓存
        _TOKEN_CACHE["token"] = data["tenant_access_token"]
        _TOKEN_CACHE["expires_at"] = current_time + data.get("expire", 7200)
        return _TOKEN_CACHE["token"]
    else:
        print(f"❌ 获取飞书 Token 失败: {data}")
        return None

def extract_feishu_text(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value.strip()
    
    text_parts = []
    def _dfs(obj):
        if isinstance(obj, dict):
            if 'text' in obj and isinstance(obj['text'], str):
                text_parts.append(obj['text'])
            elif 'value' in obj and isinstance(obj['value'], str):
                text_parts.append(obj['value'])
            for k, v in obj.items():
                _dfs(v)
        elif isinstance(obj, list):
            for item in obj:
                _dfs(item)

    _dfs(value)
    if text_parts:
        return "".join(text_parts).strip()
    return str(value).strip()


def get_crawler_configs():
    token = get_tenant_access_token()
    if not token:
        print("❌ 无法获取飞书 Token，配置读取失败")
        return []
    
    # 配置表参数
    base_id = APP_TOKEN
    table_id = TABLE_ID_CONFIG
    
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{base_id}/tables/{table_id}/records/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    configs = []
    page_token = None
    
    print("\n🔍 开始读取飞书配置表...")
    
    try:
        while True:
            payload = {"page_size": 100}
            if page_token:
                payload["page_token"] = page_token
            
            response = requests.post(url, headers=headers, json=payload, timeout=15, proxies={"http": None, "https": None}, verify=False)
            data = response.json()
            
            if data.get("code") != 0:
                print(f"❌ 读取配置表失败: {data.get('msg')}")
                break
            
            items = data.get("data", {}).get("items", [])
            for idx, item in enumerate(items):
                fields = item.get("fields", {})
                
                status_text = extract_feishu_text(fields.get("状态", ""))
                keyword = extract_feishu_text(fields.get("岗位Title", ""))
                exclude_words_raw = extract_feishu_text(fields.get("排除词", ""))
                city_text = extract_feishu_text(fields.get("城市", ""))
                salary_text = extract_feishu_text(fields.get("薪资", ""))
                
                if status_text == "启用":
                    exclude_words = []
                    if exclude_words_raw:
                        exclude_words = [w.strip() for w in re.split(r'[,，、]', exclude_words_raw) if w.strip()]
                    
                    if keyword:
                        config = {
                            'keyword': keyword,
                            'exclude_words': exclude_words,
                            'city': city_text,
                            'salary': salary_text
                        }
                        configs.append(config)
            
            if not data.get("data", {}).get("has_more", False):
                break
            page_token = data.get("data", {}).get("page_token")
        
        return configs
        
    except Exception as e:
        print(f"❌ 读取配置表异常: {e}")
        return []

def get_active_search_configs():
    token = get_tenant_access_token()
    if not token:
        return []

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID_CONFIG}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "filter": {"conjunction": "and", "conditions": [{"field_name": "状态", "operator": "contains", "value": ["启用"]}]}
    }
    
    try:
        response = requests.post(f"{url}/search", headers=headers, json=payload, timeout=15, proxies={"http": None, "https": None}, verify=False)
        data = response.json()
        if data.get("code") != 0:
            print(f"❌ 读取飞书配置失败: {data.get('msg')}")
            return []
            
        records = data.get("data", {}).get("items", [])
        configs = []
        
        for record in records:
            fields = record.get("fields", {})
            
            keyword = extract_feishu_text(fields.get("岗位Title", ""))
            city = extract_feishu_text(fields.get("城市", ""))
            salary = extract_feishu_text(fields.get("薪资", ""))
            
            exclude_str = extract_feishu_text(fields.get("排除词", ""))
            blacklist = [w.strip() for w in exclude_str.replace("，", ",").split(",") if w.strip()]
            
            if keyword:
                configs.append({
                    "keyword": keyword,
                    "city": city,
                    "salary": salary,
                    "blacklist": blacklist
                })
        return configs
    except Exception as e:
        print(f"⚠️ 连接飞书表格出错: {e}")
        return []

# 🌟 修改 2：重写为支持所有渠道的大一统万能推送函数，强制清理格式
def push_job_to_feishu(job_data):
    """大一统：推送任意渠道的岗位数据到飞书新总表"""
    token = get_tenant_access_token()
    if not token:
        return False

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID_JOBS}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 确保字段都是字符串类型，防止飞书因类型不匹配报错
    fields = {
        "岗位名称": str(job_data.get("岗位名称", "")),
        "公司名称": str(job_data.get("公司名称", "")),
        "城市": str(job_data.get("城市", "")),
        "薪资": str(job_data.get("薪资", "")),
        "岗位链接": str(job_data.get("岗位链接", "")), 
        "跟进状态": str(job_data.get("跟进状态", "新线索")),
        "工作地址": str(job_data.get("工作地址", "")),
        "抓取时间": str(job_data.get("抓取时间", "")),
        "发布日期": str(job_data.get("发布日期", "")),
        "HR活跃度": str(job_data.get("HR活跃度", "")),
        "所属行业": str(job_data.get("所属行业", "")),
        "福利标签": str(job_data.get("福利标签", "")),
        "公司规模": str(job_data.get("公司规模", "")),
        "学历要求": str(job_data.get("学历要求", "")),
        "经验要求": str(job_data.get("经验要求", "")),
        "HR技能标签": str(job_data.get("HR技能标签", "")),
        "岗位详情": str(job_data.get("岗位详情", "")),
        "公司介绍": str(job_data.get("公司介绍", "")),
        "角色": str(job_data.get("角色", "")),
        "招聘平台": str(job_data.get("招聘平台", "未知")),
        
        "初步打分": str(job_data.get("初步打分", "0")),
        "加分词": str(job_data.get("加分词", "")),
        "减分词": str(job_data.get("减分词", ""))
    }
    
    # 彻底清理空值，防止干扰飞书原有的默认逻辑
    fields = {k: v for k, v in fields.items() if v and v != "None" and v != "0"}
    payload = {"fields": fields}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15, proxies={"http": None, "https": None}, verify=False)
        data = response.json()
        if data.get("code") == 0:
            return True
        else:
            print(f"    ❌ 推送飞书失败: {data.get('msg')}")
            return False
    except Exception as e:
        print(f"    ⚠️ 推送飞书报错: {e}")
        return False


def get_existing_jobs():
    token = get_tenant_access_token()
    if not token:
        return set()

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID_JOBS}/records/search"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    existing_keys = set()
    page_token = ""
    has_more = True
    print("      ☁️ 正在连接飞书，下载云端去重记忆库...")

    while has_more:
        payload = {
            "field_names": ["公司名称", "城市", "薪资"], 
            "page_size": 500
        }
        if page_token: payload["page_token"] = page_token

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15, proxies={"http": None, "https": None}, verify=False)
            data = response.json()
            if data.get("code") != 0: break
            
            records = data.get("data", {}).get("items", [])
            for record in records:
                fields = record.get("fields", {})
                
                comp = extract_feishu_text(fields.get("公司名称", ""))
                city = extract_feishu_text(fields.get("城市", ""))
                salary = extract_feishu_text(fields.get("薪资", ""))
                
                if comp:
                    existing_keys.add(f"{comp}###{city}###{salary}")

            has_more = data.get("data", {}).get("has_more", False)
            page_token = data.get("data", {}).get("page_token", "")
        except Exception:
            break
    return existing_keys  

def get_new_leads_from_feishu():
    """
    从飞书多维表格中拉取所有【跟进状态】为"新线索"的岗位记录
    """
    token = get_tenant_access_token()
    if not token:
        return []

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID_JOBS}/records/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "filter": {
            "conjunction": "and",
            "conditions": [
                {
                    "field_name": "跟进状态",
                    "operator": "is",
                    "value": ["新线索"]
                }
            ]
        },
        # 🌟 修改 3：补齐了 "招聘平台" 字段，让 AI 评估引擎知道数据来源
        "field_names": [
            "岗位名称", "公司名称", "城市", "薪资", "岗位详情",
            "工作地址", "HR活跃度", "所属行业", "福利标签",
            "公司规模", "学历要求", "经验要求", "HR技能标签", "招聘平台",
            "初步打分", "加分词", "减分词"
        ],
        "page_size": 500
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15, proxies={"http": None, "https": None}, verify=False)
        data = response.json()
        if data.get("code") != 0:
            print(f"❌ 拉取新线索岗位失败: {data.get('msg')}")
            return []
            
        records = data.get("data", {}).get("items", [])
        new_leads = []
        for record in records:
            fields = record.get("fields", {})
            jd_text = extract_feishu_text(fields.get("岗位详情", ""))
            
            if not jd_text or len(jd_text.strip()) < 50:
                continue
            
            new_leads.append({
                "record_id": record.get("record_id"),
                "company": extract_feishu_text(fields.get("公司名称", "未知公司")),
                "job_title": extract_feishu_text(fields.get("岗位名称", "未知岗位")),
                "city": extract_feishu_text(fields.get("城市", "")),
                "salary": extract_feishu_text(fields.get("薪资", "")),
                "jd_text": jd_text,
                "platform": extract_feishu_text(fields.get("招聘平台", "未知")),
                "work_address": extract_feishu_text(fields.get("工作地址", "")),
                "hr_active": extract_feishu_text(fields.get("HR活跃度", "")),
                "industry": extract_feishu_text(fields.get("所属行业", "")),
                "welfare": extract_feishu_text(fields.get("福利标签", "")),
                "scale": extract_feishu_text(fields.get("公司规模", "")),
                "degree": extract_feishu_text(fields.get("学历要求", "")),
                "experience": extract_feishu_text(fields.get("经验要求", "")),
                "hr_skills": extract_feishu_text(fields.get("HR技能标签", "")),
                "preliminary_score": extract_feishu_text(fields.get("初步打分", "0")),
                "bonus_words": extract_feishu_text(fields.get("加分词", "")),
                "deduction_words": extract_feishu_text(fields.get("减分词", ""))
            })
        
        return new_leads
    except Exception as e:
        print(f"❌ 拉取新线索岗位出错: {e}")
        return []

def get_pending_apply_jobs():
    token = get_tenant_access_token()
    if not token:
        return []

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID_JOBS}/records/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "filter": {
            "conjunction": "and",
            "conditions": [
                {
                    "field_name": "跟进状态",
                    "operator": "contains",
                    "value": ["简历AI改写"] 
                }
            ]
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15, proxies={"http": None, "https": None}, verify=False)
        data = response.json()
        if data.get("code") != 0:
            print(f"      ⚠️ 读取准备投递岗位失败: {data.get('msg')}")
            return []
            
        records = data.get("data", {}).get("items", [])
        pending_jobs = []
        for record in records:
            fields = record.get("fields", {})
            greeting = extract_feishu_text(fields.get("打招呼语", ""))
            
            if not greeting:
                jd_full_text = extract_feishu_text(fields.get("岗位详情", ""))
                eval_report = extract_feishu_text(fields.get("AI评估结果", ""))
                
                pending_jobs.append({
                    "record_id": record.get("record_id"),
                    "company": extract_feishu_text(fields.get("公司名称", "未知公司")),
                    "job_title": extract_feishu_text(fields.get("岗位名称", "未知岗位")),
                    "platform": extract_feishu_text(fields.get("招聘平台", "未知")),
                    "jd_text": jd_full_text,
                    "evaluation_report": eval_report
                })
        return pending_jobs
    except Exception as e:
        print(f"      ⚠️ 拉取准备投递岗位出错: {e}")
        return []

def _try_load_resume_json_dict(json_str: str):
    if json_str is None:
        return None
    s = str(json_str).strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    
    backticks = "\x60\x60\x60"
    if s.startswith(backticks):
        s2 = re.sub(r"^" + backticks + r"(?:json)?\s*", "", s, flags=re.IGNORECASE).strip()
        s2 = re.sub(r"\s*" + backticks + r"\s*$", "", s2).strip()
        try:
            obj = json.loads(s2)
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None

def normalize_ai_rewrite_json_payload(raw: str) -> str:
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if _try_load_resume_json_dict(s) is not None:
        return s
        
    backticks = "\x60\x60\x60"
    if s.startswith(backticks):
        s2 = re.sub(r"^" + backticks + r"(?:json)?\s*", "", s, flags=re.IGNORECASE).strip()
        s2 = re.sub(r"\s*" + backticks + r"\s*$", "", s2).strip()
        if _try_load_resume_json_dict(s2) is not None:
            return s2
    return s

def extract_rationales_from_json(json_str: str) -> str:
    data = _try_load_resume_json_dict(json_str or "")
    if not data:
        return ""

    blocks: list[str] = []

    projects = data.get("projects")
    if isinstance(projects, list):
        for p in projects:
            if not isinstance(p, dict):
                continue
            pname = str(p.get("project_name") or "").strip() or "项目"
            lines: list[str] = []
            actions = p.get("star_a_actions")
            if isinstance(actions, list):
                for act in actions:
                    if not isinstance(act, dict):
                        continue
                    rat = act.get("rewrite_rationale")
                    if rat is None:
                        continue
                    text = str(rat).strip()
                    if not text:
                        continue
                    sub = str(act.get("subtitle") or "").strip()
                    if sub:
                        lines.append(f"· {sub}：{text}")
                    else:
                        lines.append(f"· {text}")
            if lines:
                blocks.append(f"【项目｜{pname}】\n" + "\n".join(lines))

    works = data.get("work_experience")
    if isinstance(works, list):
        for w in works:
            if not isinstance(w, dict):
                continue
            cname = str(w.get("company_name") or w.get("company") or "").strip() or "工作经历"
            lines: list[str] = []
            actions = w.get("actions")
            if isinstance(actions, list):
                for act in actions:
                    if not isinstance(act, dict):
                        continue
                    rat = act.get("rewrite_rationale")
                    if rat is None:
                        continue
                    text = str(rat).strip()
                    if not text:
                        continue
                    sub = str(act.get("subtitle") or "").strip()
                    if sub:
                        lines.append(f"· {sub}：{text}")
                    else:
                        lines.append(f"· {text}")
            if lines:
                blocks.append(f"【工作经历｜{cname}】\n" + "\n".join(lines))

    return "\n\n".join(blocks).strip()

def update_job_record(record_id, greeting, ai_rewrite_json=None, table_id=None):
    token = get_tenant_access_token()
    if not token:
        return False

    target_table_id = table_id if table_id else TABLE_ID_JOBS
    
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{target_table_id}/records/{record_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    json_payload = normalize_ai_rewrite_json_payload(
        ai_rewrite_json if ai_rewrite_json is not None else ""
    )
    rationale_text = extract_rationales_from_json(json_payload)
    
    fields = {
        "打招呼语": greeting,
        "AI改写JSON": json_payload,
        "跟进状态": "待人工复核",
    }
    if rationale_text.strip():
        fields["简历优化理由"] = rationale_text.strip()

    payload = {"fields": fields}
    
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=15, proxies={"http": None, "https": None}, verify=False)
        if response.json().get("code") == 0:
            return True
        else:
            print(f"      ⚠️ 写入多维表格失败: {response.json().get('msg')}")
            return False
    except Exception as e:
        print(f"      ⚠️ 写入请求异常: {e}")
        return False

def update_qa_fields(record_id, latest_resume_text=None, qa_report_json=None, manual_refined_resume=None, table_id=None):
    token = get_tenant_access_token()
    if not token:
        return False

    target_table_id = table_id if table_id else TABLE_ID_JOBS
    
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{target_table_id}/records/{record_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    fields = {}
    
    if latest_resume_text is not None:
        fields["最新改写简历"] = latest_resume_text
    
    if qa_report_json is not None:
        if isinstance(qa_report_json, dict):
            fields["二次质检报告"] = json.dumps(qa_report_json, ensure_ascii=False, indent=2)
        else:
            fields["二次质检报告"] = qa_report_json
    
    if manual_refined_resume is not None:
        fields["人工精修版简历"] = manual_refined_resume
    
    if not fields:
        print("⚠️ 没有需要更新的字段")
        return False
    
    payload = {"fields": fields}
    
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=15, proxies={"http": None, "https": None}, verify=False)
        if response.json().get("code") == 0:
            return True
        else:
            print(f"⚠️ 更新 QA 字段失败: {response.json().get('msg')}")
            return False
    except Exception as e:
        print(f"⚠️ 更新 QA 字段异常: {e}")
        return False

def fetch_bitable_records(table_id, record_id=None):
    tenant_access_token = get_tenant_access_token()
    if not tenant_access_token:
        print("❌ 获取 tenant_access_token 失败")
        return None

    headers = {
        "Authorization": f"Bearer {tenant_access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    if record_id:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/records/{record_id}"
        try:
            response = requests.get(url, headers=headers, timeout=15, proxies={"http": None, "https": None}, verify=False)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    return data.get("data", {}).get("record")
                else:
                    print(f"❌ 读取单条记录失败: {data.get('msg')}")
                    return None
            else:
                print(f"❌ 读取单条记录失败: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ 读取单条记录异常: {e}")
            return None
    
    print("⚠️ fetch_bitable_records: 未提供 record_id，暂不支持批量读取")
    return None

def update_feishu_record(record_id, fields_to_update, table_id=None):
    token = get_tenant_access_token()
    if not token:
        return False

    target_table_id = table_id if table_id else TABLE_ID_JOBS
    
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{target_table_id}/records/{record_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    processed_fields = {}
    for field_name, field_value in fields_to_update.items():
        if field_name == "我的复核":
            if isinstance(field_value, str):
                processed_fields[field_name] = field_value.strip()
            else:
                processed_fields[field_name] = str(field_value).strip()
        elif field_name == "跟进状态":
            if isinstance(field_value, str):
                processed_fields[field_name] = field_value.strip()
            else:
                processed_fields[field_name] = str(field_value).strip()
        else:
            processed_fields[field_name] = field_value
    
    payload = {"fields": processed_fields}
    
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=15, proxies={"http": None, "https": None}, verify=False)
        data = response.json()
        if data.get("code") == 0:
            return True
        else:
            print(f"    ❌ 更新飞书记录失败: code={data.get('code')} msg={data.get('msg')}")
            print(f"    📋 尝试写入的字段 Keys（共 {len(processed_fields)} 个）:")
            for k in processed_fields.keys():
                print(f"       · '{k}'")
            print(f"    ⚠️ 请重点核查10维度字段连字符格式，如 '高权-职级资历' 中的横线是否为半角减号（-）而非全角（－）或破折号（—）")
            return False
    except Exception as e:
        print(f"    ⚠️ 更新飞书记录报错: {e}")
        return False
# ==========================================
# 删除记录
# ==========================================
def delete_feishu_record(app_token: str, table_id: str, record_id: str) -> bool:
    """调用飞书 API 永久删除多维表格中的一条记录"""
    import requests
    try:
        # ⚠️ 注意：这里调用的是你文件里已有的获取 Token 的函数。
        # 如果你之前获取 token 的函数名叫别的（比如 get_access_token），请把下面这行改对！
        access_token = get_tenant_access_token() 
        
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.delete(url, headers=headers, timeout=15, proxies={"http": None, "https": None}, verify=False)
        result = response.json()
        
        if result.get("code") == 0:
            print(f"✅ 成功删除记录: {record_id}")
            return True
        else:
            print(f"❌ 飞书 API 删除失败: {result}")
            return False
    except Exception as e:
        print(f"❌ 删除请求异常: {str(e)}")
        return False

# ==========================================
# 🌟 新增：向飞书表格插入一条全新记录
# ==========================================
def create_feishu_record(fields_data: dict, table_id: str) -> bool:
    """在飞书多维表格中新增一条记录"""
    import requests
    token = get_tenant_access_token()
    if not token:
        print("❌ 插入记录失败：无法获取 Token")
        return False
        
    # 注意：这里我们默认你在这个文件顶部定义了全局变量 APP_TOKEN
    # 如果没有，请像 delete 函数那样动态传入 app_token，或者从 config 导入
    from config import FEISHU_APP_TOKEN
    
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post(url, headers=headers, json={"fields": fields_data}, timeout=10, proxies={"http": None, "https": None}, verify=False)
        data = resp.json()
        if data.get("code") == 0:
            print(f"✅ 成功极速录入新岗位: {fields_data.get('公司名称', '未知')} - {fields_data.get('岗位名称', '未知')}")
            return True
        else:
            print(f"❌ 飞书插入失败: {data.get('msg')}")
            return False
    except Exception as e:
        print(f"❌ 飞书插入请求异常: {str(e)}")
        return False


# ==========================================
# 🌟 搜索配置表操作（动态调度回写闭环）
# ==========================================

def get_enabled_search_config() -> dict | None:
    """检索搜索配置表中状态为"启用"的第一条记录，返回 record_id 及关键字段"""
    token = get_tenant_access_token()
    if not token:
        print("❌ 无法获取 Token，搜索配置读取失败")
        return None

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID_CONFIG}/records/search"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "filter": {
            "conjunction": "and",
            "conditions": [{"field_name": "状态", "operator": "is", "value": ["启用"]}]
        },
        "page_size": 1
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10, proxies={"http": None, "https": None}, verify=False)
        data = response.json()
        if data.get("code") != 0:
            print(f"❌ 读取搜索配置失败: {data.get('msg')}")
            return None

        items = data.get("data", {}).get("items", [])
        if not items:
            return None

        record = items[0]
        fields = record.get("fields", {})
        raw_count = fields.get("抓取数量", 0)
        count = int(raw_count) if isinstance(raw_count, (int, float)) else 0

        return {
            "record_id": record.get("record_id"),
            "岗位Title": extract_feishu_text(fields.get("岗位Title", "")),
            "城市": extract_feishu_text(fields.get("城市", "")),
            "薪资": extract_feishu_text(fields.get("薪资", "")),
            "抓取数量": count
        }
    except Exception as e:
        print(f"❌ 读取搜索配置异常: {e}")
        return None


def update_search_config_count(record_id: str, current_count: int, added_count: int) -> bool:
    """将本次入库量累加到搜索配置表对应记录的"抓取数量"字段"""
    token = get_tenant_access_token()
    if not token:
        return False

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID_CONFIG}/records/{record_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"fields": {"抓取数量": current_count + added_count}}

    try:
        response = requests.put(url, headers=headers, json=payload, timeout=10, proxies={"http": None, "https": None}, verify=False)
        data = response.json()
        if data.get("code") == 0:
            print(f"✅ 搜索配置回写成功：抓取数量更新为 {current_count + added_count}")
            return True
        else:
            print(f"❌ 搜索配置回写失败: {data.get('msg')}")
            return False
    except Exception as e:
        print(f"❌ 搜索配置回写异常: {e}")
        return False


def create_search_config(title: str, city: str, salary: str, count: int) -> bool:
    """在搜索配置表新增一条记录，状态标记为"已使用"，用于临时指令的回写"""
    token = get_tenant_access_token()
    if not token:
        return False

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID_CONFIG}/records"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "fields": {
            "岗位Title": title,
            "城市": city,
            "薪资": salary,
            "状态": "已使用",
            "抓取数量": count
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10, proxies={"http": None, "https": None}, verify=False)
        data = response.json()
        if data.get("code") == 0:
            print(f"✅ 搜索配置新建成功：[{city}] [{title}]，入库 {count} 条")
            return True
        else:
            print(f"❌ 搜索配置新建失败: {data.get('msg')}")
            return False
    except Exception as e:
        print(f"❌ 搜索配置新建异常: {e}")
        return False


def get_my_preferences() -> str:
    """
    从飞书"我的求职偏好与底线"子表读取【启用】状态的偏好记录，
    拼接成带标签的结构化字符串供 LLM 参考。
    """
    try:
        from config import FEISHU_APP_TOKEN, FEISHU_TABLE_ID_PREFERENCES
        if not FEISHU_TABLE_ID_PREFERENCES:
            print("⚠️ 未配置 FEISHU_TABLE_ID_PREFERENCES，跳过偏好加载")
            return ""

        token = get_tenant_access_token()
        if not token:
            return ""

        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID_PREFERENCES}/records/search"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "filter": {
                "conjunction": "and",
                "conditions": [{"field_name": "状态", "operator": "is", "value": ["启用"]}]
            }
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=10, proxies={"http": None, "https": None}, verify=False)
        resp_json = resp.json()
        items = resp_json.get("data", {}).get("items", [])

        if not items:
            print(f"⚠️ 飞书偏好表中没有【启用】状态的记录，API code={resp_json.get('code')} msg={resp_json.get('msg')}")
            return ""

        parts = []
        for item in items:
            fields = item.get("fields", {})
            # 🔍 调试：首条记录打印所有 key，用于核对实际表头
            if not parts:
                print(f"   [偏好表] 首条记录字段 keys: {list(fields.keys())}")
            label = extract_feishu_text(fields.get("偏好类型", ""))
            content = extract_feishu_text(fields.get("具体要求", ""))
            if label and content:
                parts.append(f"[{label}]：{content}")
            elif content:
                parts.append(content)
            elif label:
                parts.append(f"[{label}]")

        if not parts:
            print("⚠️ 偏好表有记录，但 '偏好类型'/'具体要求' 字段均为空，请核对表头名称")
            return ""

        result = "\n".join(parts)
        print(f"✅ 求职偏好加载成功，共 {len(parts)} 条")
        return result

    except Exception as e:
        print(f"⚠️ 读取求职偏好失败: {e}")
        return ""


def download_feishu_file(file_token: str, save_path: str) -> bool:
    """下载飞书附件到本地路径。

    Args:
        file_token: 飞书文件 token（来自附件字段的 file_token）。
        save_path:  本地保存路径（含文件名）。

    Returns:
        True 表示下载并写入成功，False 表示失败。
    """
    token = get_tenant_access_token()
    if not token:
        print("❌ download_feishu_file：无法获取 Token")
        return False

    url = f"https://open.feishu.cn/open-apis/drive/v1/medias/{file_token}/download"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(url, headers=headers, timeout=60, stream=True, proxies={"http": None, "https": None}, verify=False)
        if response.status_code != 200:
            print(f"❌ download_feishu_file：HTTP {response.status_code}，file_token={file_token}")
            return False

        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"✅ 文件下载成功：{save_path}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ download_feishu_file 网络请求异常：{e}")
        return False
    except OSError as e:
        print(f"❌ download_feishu_file 文件写入异常：{e}")
        return False


def get_jobs_to_deliver(target_platform="猎聘", target_status="待投递"):
    """获取所有已准备好投递的岗位（提取链接、PDF Token和打招呼语）"""
    token = get_tenant_access_token()
    if not token: return []

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID_JOBS}/records/search"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 飞书 API 不支持嵌套的 AND/OR，这里只做基础状态过滤，时间判断在 Python 内完成
    payload = {
        "filter": {
            "conjunction": "and",
            "conditions": [
                {"field_name": "跟进状态", "operator": "is", "value": [target_status]},
                {"field_name": "招聘平台", "operator": "contains", "value": [target_platform]}
            ]
        },
        "page_size": 100
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15, proxies={"http": None, "https": None}, verify=False)
        data = response.json()
        if data.get("code") != 0:
            print(f"❌ 拉取待投递岗位失败: {data.get('msg')}")
            return []

        current_ts = int(time.time() * 1000)
        jobs = []
        for record in data.get("data", {}).get("items", []):
            fields = record.get("fields", {})

            # 🌟 Python 内进行定时投递时间拦截：空=立即投递；非空则需 <= 当前时间
            scheduled_time = fields.get("定时投递时间")
            if scheduled_time:
                try:
                    if int(scheduled_time) > current_ts:
                        print(f"⏰ 记录 {record.get('record_id')} 定时投递时间未到，已跳过")
                        continue
                except Exception:
                    pass  # 时间解析失败时不阻塞，照常投递

            # 1. 解析 PDF 附件 Token 和名字
            pdf_attachments = fields.get("PDF备份", [])
            file_token = ""
            pdf_name = "专属简历"
            if pdf_attachments and isinstance(pdf_attachments, list):
                file_token = pdf_attachments[0].get("file_token", "")
                pdf_name = pdf_attachments[0].get("name", "专属简历").replace(".pdf", "")

            # 2. 解析岗位链接
            job_link_obj = fields.get("岗位链接", {})
            job_url = ""
            if isinstance(job_link_obj, dict):
                job_url = job_link_obj.get("link", "")
            else:
                job_url = str(job_link_obj)

            # 3. 获取打招呼语
            greeting = extract_feishu_text(fields.get("打招呼语", ""))

            # 提取图片版简历附件列表（供 BOSS 投递引擎使用）
            image_attachments = fields.get("图片保存", [])
            image_items = []
            if image_attachments and isinstance(image_attachments, list):
                for att in image_attachments:
                    token = att.get("file_token", "")
                    if token:
                        image_items.append({"file_token": token, "name": att.get("name", "image.jpg")})

            # 只有当必备要素齐全时，才认为该岗位合法
            if job_url and (file_token or image_items) and greeting:
                jobs.append({
                    "record_id": record.get("record_id"),
                    "job_url": job_url,
                    "file_token": file_token,
                    "pdf_name": pdf_name,
                    "greeting": greeting,
                    "image_items": image_items,
                    "company": extract_feishu_text(fields.get("公司名称", "")),
                    "job_title": extract_feishu_text(fields.get("岗位名称", "")),
                    "scheduled_at": fields.get("定时投递时间")
                })
            else:
                print(f"⚠️ 记录 {record.get('record_id')} 数据不全(缺URL/PDF或图片/开场白)，已跳过")

        return jobs
    except Exception as e:
        print(f"❌ 请求拉取待投递岗位时异常: {e}")
        return []


def batch_delete_feishu_records(record_ids: list, table_id: str = TABLE_ID_JOBS) -> bool:
    """批量删除飞书多维表格记录"""
    if not record_ids:
        return True

    token = get_tenant_access_token()
    if not token:
        print("❌ batch_delete_feishu_records：无法获取 Token")
        return False

    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/records/batch_delete"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"records": record_ids}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15, proxies={"http": None, "https": None}, verify=False)
        data = response.json()
        if data.get("code") == 0:
            print(f"✅ 成功从飞书批量删除 {len(record_ids)} 条记录")
            return True
        else:
            print(f"❌ 飞书批量删除失败: {data}")
            return False
    except Exception as e:
        print(f"❌ 请求批量删除飞书记录时异常: {e}")
        return False