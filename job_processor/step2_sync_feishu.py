import sys
import os
import sqlite3
import requests
import json

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from common import feishu_api
except ImportError:
    feishu_api = None
    print("⚠️ 警告：未检测到 common/feishu_api 模块，飞书同步功能将被禁用。")

try:
    from common.config import FEISHU_APP_TOKEN, FEISHU_TABLE_ID_JOBS
    NEW_APP_TOKEN = FEISHU_APP_TOKEN
    NEW_TABLE_ID = FEISHU_TABLE_ID_JOBS
except ImportError:
    NEW_APP_TOKEN = ""
    NEW_TABLE_ID = ""
    print("⚠️ 警告：未找到 config.py，飞书表格 Token 未配置。")

def push_single_record_to_feishu(token, feishu_fields):
    """
    单条推送数据到新的飞书多维表格
    """
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{NEW_APP_TOKEN}/tables/{NEW_TABLE_ID}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 清理 None 值，防止飞书报错
    cleaned_fields = {k: v for k, v in feishu_fields.items() if v is not None and v != ""}
    
    payload = {"fields": cleaned_fields}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        if data.get("code") == 0:
            print(f"✅ 推送成功: {cleaned_fields.get('公司名称', '未知')} - {cleaned_fields.get('岗位名称', '未知')}")
            return True
        else:
            print(f"❌ 推送失败 [{cleaned_fields.get('公司名称')}]: {data.get('msg')}")
            return False
    except Exception as e:
        print(f"⚠️ 请求异常: {e}")
        return False

def sync_sqlite_to_feishu(db_path, table_name="jobs"):
    """
    从 SQLite 读取满足条件的数据，并推送到飞书（带防重复同步机制）
    """
    if feishu_api is None:
        print("⚠️ 未配置飞书 API，跳过飞书同步步骤。")
        return
    token = feishu_api.get_tenant_access_token()
    if not token:
        print("🚨 无法获取飞书 Token，停止推送。")
        return

    if not os.path.exists(db_path):
        print(f"🚨 找不到数据库文件: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  
    cursor = conn.cursor()

    # 🌟 步骤 1：智能检查并添加 is_synced 列（如果数据库里还没有这个字段的话）
    try:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN is_synced INTEGER DEFAULT 0")
        conn.commit()
        print("💡 数据库已自动升级，新增『is_synced』同步状态追踪字段。")
    except sqlite3.OperationalError:
        # 如果报错，说明字段已经存在，直接忽略
        pass

    # 🌟 步骤 2：编写 SQL 查询（增加 is_synced = 0 的过滤条件）
    sql_query = f"""
        SELECT * FROM {table_name} 
        WHERE platform IN ('51job', 'boss直聘', 'BOSS直聘', 'Boss直聘', '猎聘') 
        AND keywords_score > 0
        AND (is_synced = 0 OR is_synced IS NULL)
    """
    
    try:
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        
        if len(rows) == 0:
            print("✅ 当前没有需要同步的新岗位（历史符合条件的岗位均已同步完毕）。")
            return
            
        print(f"🔍 查找到 {len(rows)} 条【未同步】且符合条件的高分岗位，准备推送...")
        
        for row in rows:
            job_data = dict(row)
            job_link = job_data.get("job_link", "")
            feishu_link_format = {"link": job_link, "text": "点击查看岗位"} if job_link else ""
            
            try:
                score = float(job_data.get("keywords_score", 0))
            except (ValueError, TypeError):
                score = 0
                
            feishu_fields = {
                "岗位链接": feishu_link_format,
                "岗位名称": job_data.get("job_title", ""),
                "公司名称": job_data.get("company_name", ""),
                "城市": job_data.get("city", ""),
                "岗位详情": job_data.get("jd_text", ""),
                "薪资": job_data.get("salary", ""),
                "工作地址": job_data.get("work_address", ""),
                "HR活跃度": job_data.get("hr_activity", ""),
                "所属行业": job_data.get("industry", ""),
                "福利标签": job_data.get("welfare_tags", ""),
                "公司规模": job_data.get("company_size", ""),
                "学历要求": job_data.get("education_req", ""),
                "经验要求": job_data.get("experience_req", ""),
                "HR技能标签": job_data.get("hr_skill_tags", ""),
                "公司介绍": job_data.get("company_intro", ""),
                "角色": job_data.get("role", ""),
                "发布日期": job_data.get("publish_date", ""),
                "招聘平台": job_data.get("platform", ""),
                "抓取时间": job_data.get("crawl_time", ""),
                "初步打分": score,
                "加分词": job_data.get("positive_hits", ""),
                "减分词": job_data.get("negative_hits", ""),
                "跟进状态": "新线索" 
            }
            
            # 🌟 步骤 3：执行单条推送，成功后立刻将本地数据库状态改为【已同步】
            success = push_single_record_to_feishu(token, feishu_fields)
            
            if success and job_link:
                update_sql = f"UPDATE {table_name} SET is_synced = 1 WHERE job_link = ?"
                cursor.execute(update_sql, (job_link,))
                conn.commit()
            
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
    finally:
        cursor.close()
        conn.close()
        print("🏁 同步任务执行完毕。")

if __name__ == "__main__":
    DB_FILE_PATH = os.path.join(PROJECT_ROOT, "data", "job_hunter.db")
    TABLE_NAME = "raw_jobs"

    sync_sqlite_to_feishu(DB_FILE_PATH, table_name=TABLE_NAME)