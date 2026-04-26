import subprocess
import sys
import time
import random
import csv
import io
import os
import datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ai_scorer import get_job_match_score, rewrite_resume_for_job, generate_greeting
# 🌟 这里引入了我们 feishu_api.py 中最新的功能函数
from common.feishu_api import (
    get_active_search_configs,
    push_job_to_feishu,
    get_existing_jobs,
    normalize_ai_rewrite_json_payload,
    extract_rationales_from_json,
)
from boss_scraper.boss_detail_fetcher import fetch_job_detail, is_toxic_job

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def refresh_real_edge():
    print("      🔄 [机械臂] 激活 Edge 浏览器...")
    apple_script = '''
    tell application "Microsoft Edge"
        activate
        reload active tab of window 1
    end tell
    delay 6 
    tell application "System Events"
        key code 125
        delay 0.8
        key code 125
        delay 1.2
        key code 126
    end tell
    '''
    subprocess.run(["osascript", "-e", apple_script])
    sleep_time = random.randint(12, 22)
    print(f"      ⏳ [机械臂] 正在模拟浏览防风控，等待 {sleep_time} 秒...")
    time.sleep(sleep_time)

def start_patrol():
    print("🚀 启动【影帝级】全自动巡逻矩阵...\n")
    
    print("🧠 正在同步飞书云端记忆库...")
    seen_jobs = get_existing_jobs()
    print(f"✅ 云端记忆同步成功！飞书上已有 {len(seen_jobs)} 个历史岗位，本次将绝对免疫这些岗位。")

    print("📡 正在获取今日的巡逻指令...")
    search_tasks = get_active_search_configs()
    
    if not search_tasks:
        print("🤷‍♂️ 飞书中没有找到【✅启用】的任务，今天可以摸鱼了！")
        return

    print("-" * 30)
    for task in search_tasks:
        print(f"🎯 目标: {task['keyword']} | 城市: {task['city']} | 黑名单: {task.get('blacklist', [])}")
    print("-" * 30)
    
    try:
        resume_path = os.path.join(BASE_DIR, 'resume.txt')
        with open(resume_path, 'r', encoding='utf-8') as f:
            resume_text = f.read()
        print("📄 简历原件读取成功，AI 已准备好进行匹配！")
    except FileNotFoundError:
        print("❌ 找不到 resume.txt，请确保它和本脚本在同一个文件夹下！")
        return
    
    for i, task in enumerate(search_tasks):
        keyword = task['keyword']
        city = task['city']
        salary = task['salary']
        my_blacklist = task.get('blacklist', [])
        
        print(f"\n{'='*40}")
        print(f"🎯 [{i+1}/{len(search_tasks)}] 准备执行飞书任务：【{keyword} - {city}】")
        
        refresh_real_edge()
            
        print(f"🕸️ 开始批量检索大盘数据...")
        command_list = ["boss", "export", keyword]
        
        if city:
            command_list.extend(["--city", city]) 
        if salary:
            command_list.extend(["--salary", salary])
            
        export_result = subprocess.run(command_list, capture_output=True, text=True)
        
        if export_result.returncode == 0:
            csv_content = export_result.stdout.strip()
            lines = csv_content.split('\n')
            
            if len(lines) > 1:
                reader = csv.DictReader(io.StringIO(csv_content))
                
                for row in reader:
                    security_id = row.get('securityId', row.get('\ufeffsecurityId', row.get('职位ID', row.get('job_url', ''))))
                    if not security_id:
                        continue
                    
                    job_title = row.get('职位', row.get('职位名称', row.get('name', row.get('jobName', '未知岗位'))))
                    company_name = row.get('公司', row.get('公司名称', row.get('company', row.get('brandName', '未知公司'))))
                    
                    current_city = city if city else row.get('cityName', '未知')
                    current_salary = row.get('salaryDesc', row.get('薪资', '面议'))
                    unique_job_key = f"{company_name}###{current_city}###{current_salary}"
                    
                    if unique_job_key in seen_jobs:
                        continue

                    print(f"   ✨ 发现全新未收录岗位: {company_name} - {job_title}")
                    print("      🕵️ 正在潜入后台获取完整详情与全维数据...")
                    
                    full_desc, address, encrypt_id, extra_info = fetch_job_detail(security_id, on_captcha_callback=refresh_real_edge)
                    
                    if not full_desc:
                        print("      ⚠️ 详情抓取为空，放弃评估。")
                        continue
                        
                    is_toxic, matched_word = is_toxic_job(job_title, full_desc, row, my_blacklist)
                    if is_toxic:
                        print(f"      🚫 拦截成功！命中黑名单关键词:【{matched_word}】，直接丢弃！")
                        seen_jobs.add(unique_job_key)
                        time.sleep(random.randint(2, 5))
                        continue
                    
                    skills_str = "未提及"
                    try:
                        print(f"      🧠 [1/5] 正在呼叫 AI 进行深度评估...")
                        ai_result = get_job_match_score(resume_text, full_desc)

                        skills_list = ai_result.get('extracted_skills', [])
                        if isinstance(skills_list, list):
                            skills_str = ", ".join(str(item) for item in skills_list) if skills_list else "未提及"
                        else:
                            skills_str = str(skills_list)

                        ai_total = int(ai_result.get('total_score', 0))
                        print(f"      📊 [2/5] 诊断报告已出！✅ AI 综合得分: {ai_total}分")

                        rewritten_json_str = ""
                        greeting_text = ""
                        
                        if ai_total >= 85:
                            print(f"      🔥 [3/5] 触发【自动轨】！正在定制简历与打招呼语...")
                            # 生成改写简历
                            rewritten_json_str = rewrite_resume_for_job(resume_text, full_desc, ai_result)
                            # 生成打招呼语
                            greeting_text = generate_greeting(resume_text, full_desc)
                            print(f"      🎉 [4/5] 定制完毕，准备入库。")
                        else:
                            print(f"      ⏸️ [3/5] 触发【人工轨】(<85分)！仅保存评分报告。")
                            print(f"      👀 [4/5] 状态设为 [新线索]。")

                    except Exception as e:
                        print(f"      ❌ AI 诊断阶段报错: {e}")
                        continue
                    
                    print(f"      📦 [5/5] 正在将数据推送到飞书中台...")
                    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # 🌟 核心修复点：使用正确的变量名 rewritten_json_str 进行处理
                    norm_resume_json = ""
                    rationale_text = ""
                    if rewritten_json_str:
                        norm_resume_json = normalize_ai_rewrite_json_payload(rewritten_json_str)
                        rationale_text = extract_rationales_from_json(norm_resume_json)

                    feishu_data = {
                        "岗位名称": job_title,
                        "公司名称": company_name,
                        "城市": current_city,
                        "薪资": current_salary,
                        "岗位链接": {"link": f"https://www.zhipin.com/job_detail/{encrypt_id}.html", "text": "点击投递"},
                        "跟进状态": "新线索" if ai_total < 85 else "准备投递", 
                        "工作地址": address,  
                        "抓取时间": current_time_str,
                        "HR活跃度": extra_info.get("hr_active", ""),
                        "所属行业": extra_info.get("industry", ""),
                        "福利标签": extra_info.get("welfare", ""),
                        "公司规模": extra_info.get("scale", ""),
                        "学历要求": extra_info.get("degree", ""),
                        "经验要求": extra_info.get("experience", ""),
                        "HR技能标签": extra_info.get("hr_skills", ""),
                        "岗位详情": full_desc,
                        
                        # AI 改写内容与理由
                        "AI改写JSON": norm_resume_json,
                        "简历优化理由": rationale_text,
                        "打招呼语": greeting_text,

                        # AI 深度诊断数据
                        "AI总分": ai_total,
                        "背景得分": int(ai_result.get('bg_score', 0)),
                        "技能得分": int(ai_result.get('skill_score', 0)),
                        "经验得分": int(ai_result.get('exp_score', 0)),
                        "技能要求": skills_str,
                        "理想画像与能力信号": str(ai_result.get('dream_picture', '')),
                        "核心能力词典": str(ai_result.get('ats_ability_analysis', '')),
                        "高杠杆匹配点": str(ai_result.get('strong_fit_assessment', '')),
                        "致命硬伤与毒点": str(ai_result.get('risk_red_flags', '')),
                        "破局行动计划": str(ai_result.get('deep_action_plan', ''))
                    }

                    is_success = push_job_to_feishu(feishu_data)
                    if is_success:
                        print(f"      🚀 成功推送到飞书看板！")
                        seen_jobs.add(unique_job_key)
                    
                    sleep_time = random.randint(10, 20)
                    time.sleep(sleep_time)

            else:
                print(f"⚠️ 抓取结果为空。")
        else:
            print(f"❌ 抓取报错：{export_result.stderr}")
        
        if i < len(search_tasks) - 1:
            time.sleep(random.randint(5, 10))

    print("\n🏁 巡逻矩阵任务全部处理完毕！")

if __name__ == "__main__":
    start_patrol()