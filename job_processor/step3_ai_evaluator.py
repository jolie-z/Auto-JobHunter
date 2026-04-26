import sqlite3
import os
from structural_filter import StructuralFilterEngine

def run_db_filter():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    # 根据你的项目结构调整路径
    abs_db_path = os.path.join(parent_dir, "data", "job_hunter.db")
    
    if not os.path.exists(abs_db_path):
        # 兼容当前目录情况
        abs_db_path = os.path.join(current_dir, "data", "job_hunter.db")
        if not os.path.exists(abs_db_path):
            print(f"❌ 找不到数据库文件: {abs_db_path}")
            return

    print("🧹 [阶段一] 启动 Python 结构化漏斗粗筛...")
    
    conn = sqlite3.connect(abs_db_path)
    cursor = conn.cursor()
    
    engine = StructuralFilterEngine()
    
    # 提取所有刚存入的原始数据
    cursor.execute("SELECT job_link, job_title, experience_req, education_req FROM raw_jobs WHERE process_status = '已存入数据'")
    rows = cursor.fetchall()
    
    reject_data = []
    pass_data = []
    
    for job_link, job_title, experience_req, education_req in rows:
        is_garbage, reason = engine.is_obvious_garbage(job_title, experience_req, education_req)
        
        if is_garbage:
            reject_data.append(('清洗淘汰', f"【Python拦截】{reason}", job_link))
        else:
            # 通过粗筛的，标记为待推送飞书（或者待打分）
            pass_data.append(('待推送飞书', job_link))
            
    if reject_data:
        cursor.executemany("UPDATE raw_jobs SET process_status = ?, reject_reason = ? WHERE job_link = ?", reject_data)
        print(f"🚫 粗筛拦截：已直接淘汰 {len(reject_data)} 个垃圾岗位！")
        
    if pass_data:
        cursor.executemany("UPDATE raw_jobs SET process_status = ? WHERE job_link = ?", pass_data)
        print(f"✅ 粗筛放行：有 {len(pass_data)} 个高质量岗位进入下一环节。")

    conn.commit()
    conn.close()
    print("✨ 数据库粗筛处理完成！")

if __name__ == "__main__":
    run_db_filter()
