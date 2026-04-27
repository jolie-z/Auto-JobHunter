import sqlite3
import os

# 🌟 核心路径定义：自动定位到脚本所在目录 (data 文件夹)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(CURRENT_DIR, 'job_hunter.db')

def init_detailed_db():
    """
    初始化 Auto-Job-Hunter 系统的核心数据库底座。
    
    功能亮点：
    1. 自动容错：自动创建 data 目录，防止首次运行崩溃。
    2. 并发增强：开启 WAL 模式，支持爬虫抓取与数据清洗脚本同时运行。
    3. 全量字段：一次性建立包含采集信息与业务逻辑的 25 个核心字段。
    """
    # 确保 data 文件夹存在
    if not os.path.exists(CURRENT_DIR):
        os.makedirs(CURRENT_DIR, exist_ok=True)
        
    print(f"📦 正在扫描数据库环境...")
    print(f"📍 数据库目标位置: {DB_PATH}")

    try:
        # 🌟 改进点 1：加入 timeout 参数，防止多进程（如三个平台同时抓取）写入时锁死
        conn = sqlite3.connect(DB_PATH, timeout=30)
        
        # 🌟 改进点 2：开启 WAL (Write-Ahead Logging) 模式
        # 这允许你在使用 DataGrip 或脚本分析数据的同时，爬虫依然能顺利写入数据，互不干扰
        conn.execute("PRAGMA journal_mode=WAL;")
        
        cursor = conn.cursor()

        # 创建包含 25 个字段的原始岗位表 (19个采集字段 + 6个清洗逻辑字段)
        # 使用 job_link 作为 PRIMARY KEY 进行天然去重
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS raw_jobs (
                -- A. 基础采集维度 (19个)
                job_link TEXT PRIMARY KEY,       -- 岗位链接 (全网唯一标识)
                job_title TEXT,                  -- 岗位名称
                company_name TEXT,               -- 公司名称
                city TEXT,                       -- 城市
                jd_text TEXT,                    -- 岗位详情 (LLM 评估的核心语料)
                salary TEXT,                     -- 薪资描述
                work_address TEXT,               -- 精确上班地址
                hr_activity TEXT,                -- HR 活跃度
                industry TEXT,                   -- 所属行业
                welfare_tags TEXT,               -- 福利标签
                company_size TEXT,               -- 公司规模
                education_req TEXT,              -- 学历要求
                experience_req TEXT,             -- 经验要求
                hr_skill_tags TEXT,              -- HR 技能标签
                company_intro TEXT,              -- 公司介绍
                role TEXT,                       -- 招聘者角色 (HR/经理/猎头)
                publish_date TEXT,               -- 岗位发布/更新日期
                platform TEXT,                   -- 招聘平台 (Boss/51job/Liepin)
                crawl_time DATETIME DEFAULT (datetime('now', 'localtime')), -- 抓取时间
                
                -- B. 业务逻辑与状态流转维度 (6个，已整合自原 1_init_db.py)
                process_status TEXT DEFAULT '已存入数据', -- 状态：已存入/清洗淘汰/待打分/已同步
                keywords_status TEXT,                   -- 规则筛选状态 (PASS / REJECT)
                keywords_score REAL,                    -- 关键词匹配总分
                positive_hits TEXT,                     -- 命中的加分词项
                negative_hits TEXT,                     -- 命中的减分词项
                reject_reason TEXT                      -- 详细淘汰原因
            )
        ''')
        
        conn.commit()
        conn.close()
        
        print(f"✅ 数据库初始化/校验成功！")
        print(f"🚀 [Auto-Job-Hunter] 核心底座已准备就绪，可以开始多平台数据收割。")

    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")

if __name__ == "__main__":
    init_detailed_db()