#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
自然语言驱动的 51job (前程无忧) 动态目标调度大管家

功能：
1. 目标驱动：设定目标入库数量（如50个），程序自动翻页抓取直至满足条件。
2. 实时监听：截获底层爬虫输出，实时累加进度。
3. 纯净防止乱码解析。
"""

import os
import sys
import json
import time
import random
import subprocess
import re
from openai import OpenAI

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from common.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
except ImportError:
    print("❌ 错误：未找到 config.py。请在项目根目录根据 config_example.py 创建。")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

# 🌟 修改系统提示词，提取 target_jobs
INTENT_SYSTEM_PROMPT = """你是一个 51job(前程无忧) 爬虫调度助手。
请将用户的指令解析成以下严格的 JSON 格式，不要输出任何其他内容或说明文字：
{
  "keyword": "搜索关键词（字符串）",
  "city": "城市名称（字符串，如广州/深圳/杭州等，未提及则填'全国'）",
  "salary": "薪资描述（字符串，如10-15K/1.5万-2万，未提及则填'不限'）",
  "start_page": 起始页码（整数，默认1）,
  "target_jobs": 期望成功入库的岗位数量 (整数，如果用户要求抓X页，按一页50个估算为 X*50；如果直接要求抓X个，则填X)
}"""

def parse_intent(user_input):
    print(f">> 🧠 正在解析指令：{user_input}")
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        clean_json = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f">> ❌ 指令解析失败: {e}")
        return None

def countdown_sleep(seconds):
    print(f"\n   💤 翻页大休眠，计划等待 {seconds} 秒（约 {seconds // 60} 分钟）...")
    for i in range(seconds, 0, -1):
        if i % 30 == 0 or i <= 5:
            print(f"   ⏳ [潜行防风控中] 还剩 {i} 秒...", end='\r', flush=True)
        time.sleep(1)
    print("\n   ✅ 休眠结束，启动下一页任务！\n")

def run_task(keyword, city, start_page, target_jobs, salary):
    """🌟 动态 While 循环，实时解析 51job 终端日志"""
    crawler_path = os.path.join(CURRENT_DIR, "51job_collector.py")
    
    total_inserted = 0
    current_page = start_page
    
    while total_inserted < target_jobs:
        print(f"\n{'=' * 60}")
        print(f"🎯 进度: 已入库 {total_inserted}/{target_jobs} 个 | 正在执行: 第 {current_page} 页")
        print(f"📌 条件: 平台=51job | 职位={keyword} | 城市={city} | 薪资={salary}")

        cmd = [
            sys.executable, "-u", crawler_path,  # 🌟 必须加 -u 防止缓冲卡死
            "--platform", "51job",
            "-p", str(current_page),
            "--keyword", keyword
        ]
        if city and city != "全国": cmd.extend(["--city", city])
        if salary and salary != "不限": cmd.extend(["--salary", salary])

        process = subprocess.Popen(
            cmd, cwd=CURRENT_DIR,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8'
        )
        
        page_inserted = 0
        hit_bottom = False
        
        for line in process.stdout:
            print(line, end="")
            
            # 捕获 51job 的入库日志: "🎯 本页成功采集并入库 X 条数据。"
            match = re.search(r"入库 (\d+) 条数据", line)
            if match:
                page_inserted = int(match.group(1))
                
            # 捕获到底部的日志
            if "已到达最后一页" in line or "无任何岗位数据" in line:
                hit_bottom = True
                
        process.wait()
        total_inserted += page_inserted
        
        if hit_bottom:
            print(f"\n>> ⚠️ 触发熔断：51job 已无更多相关数据。")
            break
            
        if total_inserted >= target_jobs:
            print(f"\n>> 🎉 目标达成！累计已入库 {total_inserted} 个岗位 (目标: {target_jobs})。")
            break
            
        current_page += 1
        countdown_sleep(random.randint(250, 400))

    print(f"\n🏁 本轮指令已全部执行完毕！最终入库: {total_inserted}")

def main():
    print("=" * 60)
    print("💼 51job 动态目标调度大管家 已启动")
    print("   示例：帮我搜广州的数据分析，15-20K，抓50个，从第1页开始")
    print("=" * 60)

    COOKIE_FILE = os.path.join(CURRENT_DIR, '51job_cookies.json')
    if os.path.exists(COOKIE_FILE):
        print("✅ 已检测到 Cookie 文件 (51job_cookies.json)。")
    else:
        print("⚠️ 警告：未检测到 Cookie 文件！请注意可能弹出的登录验证。")

    while True:
        try:
            user_input = input("\n请输入抓取指令 (输入 q 退出): ").strip()
            if not user_input: continue
            if user_input.lower() == 'q': break
            
            intent = parse_intent(user_input)
            if not intent: continue
            
            kw = intent.get("keyword", "").strip()
            ct = intent.get("city", "全国").strip()
            sl = intent.get("salary", "不限").strip().upper()
            sp = int(intent.get("start_page", 1))
            tj = int(intent.get("target_jobs", 50))

            if not kw: continue
            
            print(f">> 确认任务: 关键词={kw}, 城市={ct}, 薪资={sl}, 起始页={sp}, 目标={tj}")
            run_task(kw, ct, sp, tj, sl)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"!! 异常: {e}")

if __name__ == "__main__":
    main()