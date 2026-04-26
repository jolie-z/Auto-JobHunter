#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
自然语言驱动的 猎聘大管家 (动态目标调度版)

功能：
1. 目标驱动：基于 target_jobs 设定入库目标，自动跨页抓取。
2. 实时日志监听与正则匹配入库量。
3. 针对猎聘的特性保留了 99 返回码安全熔断机制。
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

INTENT_SYSTEM_PROMPT = """你是一个猎聘爬虫调度助手。
请将用户的指令解析成以下严格的 JSON 格式，不要输出任何其他内容或说明：
{
  "keyword": "搜索关键词（字符串）",
  "city": "城市名称（字符串，如全国/北京/上海等，未提及则填全国）",
  "salary": "薪资描述（字符串，如不限/20-30K，未提及则填不限）",
  "start_page": 起始页码（整数，默认1）,
  "target_jobs": 期望成功入库的岗位数量 (整数，如果用户说抓X页，按一页40个估算为 X*40；如果直接要求抓X个，则填X)
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
    print(f"\n   💤 翻页大休眠，计划休眠 {seconds} 秒...")
    for i in range(seconds, 0, -1):
        if i % 30 == 0 or i <= 5:
            print(f"   ⏳ [防风控潜行中] 还剩 {i} 秒...", end='\r', flush=True)
        time.sleep(1)
    print("\n   ✅ 休眠结束，继续下一页抓取！\n")

def run_task(keyword, city, start_page, target_jobs, salary):
    """🌟 动态 While 循环，实时解析猎聘终端日志"""
    crawler_path = os.path.join(CURRENT_DIR, "liepin_crawler.py")
    
    total_inserted = 0
    current_page = start_page
    
    while total_inserted < target_jobs:
        print(f"\n{'=' * 60}")
        print(f"🎯 进度: 已入库 {total_inserted}/{target_jobs} 个 | 正在执行: 第 {current_page} 页")
        print(f"📌 条件: 关键词={keyword} | 城市={city} | 薪资={salary}")

        cmd = [
            sys.executable, "-u", crawler_path, # 🌟 -u 参数保持实时输出
            "-p", str(current_page),
            "--keyword", keyword
        ]
        if city: cmd.extend(["--city", city])
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
            
            # 捕获猎聘的入库日志: "🎯 第 X 页处理完毕！新增入库 X 个，拦截/跳过 X 个。"
            match = re.search(r"新增入库 (\d+) 个", line)
            if match:
                page_inserted = int(match.group(1))
                
            # 到底或被风控的标志
            if "未捕获到 API 数据" in line:
                hit_bottom = True
                
        process.wait()
        
        # 针对猎聘特殊的 99 安全熔断拦截
        if process.returncode == 99:
            print("\n🚨 检测到子进程返回 99 错误码，触发风控熔断，停止任务！")
            break
            
        total_inserted += page_inserted
        
        if hit_bottom:
            print(f"\n>> ⚠️ 触发中断：猎聘未返回数据，可能是到底部或遇到滑块验证码。")
            break
            
        if total_inserted >= target_jobs:
            print(f"\n>> 🎉 目标达成！累计已入库 {total_inserted} 个岗位 (目标: {target_jobs})。")
            break
            
        current_page += 1
        countdown_sleep(random.randint(180, 300))

    print(f"\n🏁 本轮指令执行完毕！最终入库: {total_inserted}")

def main():
    print("=" * 60)
    print("🤖 猎聘 动态目标大管家 已就绪！")
    print("   示例：帮我抓取上海的生物信息，薪资20-30K，抓40个从第3页开始")
    print("=" * 60)

    COOKIE_FILE = os.path.join(CURRENT_DIR, 'liepin_cookies.json')
    if os.path.exists(COOKIE_FILE):
        print("✅ 已检测到 Cookie 文件 (liepin_cookies.json)。")
    else:
        print("⚠️ 警告：未检测到 Cookie 文件！请确保能自动扫码登录。")

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
            tj = int(intent.get("target_jobs", 40))

            if not kw: continue
            
            print(f">> 确认任务: 关键词={kw}, 城市={ct}, 薪资={sl}, 起始页={sp}, 目标={tj}")
            run_task(kw, ct, sp, tj, sl)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"!! 异常: {e}")

if __name__ == "__main__":
    main()