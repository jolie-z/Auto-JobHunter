#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

# 初始化 OpenAI 客户端
client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

# 🌟 核心修改 1：修改系统提示词，提取“目标数量”而不是固定页数
INTENT_SYSTEM_PROMPT = """你是一个 BOSS直聘 爬虫调度助手。
请将用户的指令解析成以下严格的 JSON 格式，不要输出任何其他说明文字：
{
  "keyword": "搜索关键词",
  "city": "城市名称 (如广州/深圳等，未提及则留空)",
  "salary": "薪资描述 (如15-20K，未提及则填'不限')",
  "start_page": 起始页码 (整数，默认1),
  "target_jobs": 期望成功入库的岗位数量 (整数，如果用户说抓X页，按一页15个估算为 X*15；如果直接要求抓X个，则填X)
}"""

def parse_intent(user_input):
    """使用 LLM 解析自然语言指令"""
    print(f">> 正在解析指令: {user_input}")
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
        print(f"!! 指令解析出错: {e}")
        return None

def countdown_sleep(seconds):
    """带简单倒计时的休眠，防止频繁翻页触发风控"""
    print(f"-- 翻页大休眠: 计划等待 {seconds} 秒...")
    for i in range(seconds, 0, -1):
        if i % 30 == 0 or i <= 5:
            print(f"   [等待中] 还剩 {i} 秒...", end='\r', flush=True)
        time.sleep(1)
    print("\n-- 休眠结束，开始下一页任务。")

def run_task(keyword, city, start_page, target_jobs, salary):
    """🌟 核心修改 2：动态 While 循环，实时解析终端日志进行累加"""
    crawler_path = os.path.join(CURRENT_DIR, "boss_collector.py")
    
    total_inserted = 0
    current_page = start_page
    
    # 只要已入库数量小于目标，就一直抓下一页
    while total_inserted < target_jobs:
        print(f"\n{'='*50}")
        print(f"🎯 当前进度: 已入库 {total_inserted}/{target_jobs} 个 | 正在执行: 第 {current_page} 页")
        print(f"📌 条件: 关键词={keyword} | 城市={city} | 薪资={salary}")
        
        # 构造命令行参数
        cmd = [
            sys.executable, "-u", crawler_path,
            "--platform", "boss",
            "-p", str(current_page),
            "--keyword", keyword
        ]
        if city:
            cmd.extend(["--city", city])
        if salary and salary != "不限":
            cmd.extend(["--salary", salary])
            
        # 🌟 核心修改 3：使用 Popen 实时截获输出流，而不是直接 run
        process = subprocess.Popen(
            cmd, cwd=CURRENT_DIR, 
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
            text=True, encoding='utf-8'
        )
        
        page_inserted = 0
        hit_bottom = False
        
        # 逐行读取子脚本在终端的输出，并实时打印出来（保持你的原有体验）
        for line in process.stdout:
            print(line, end="")
            
            # 使用正则捕捉这句关键日志: "🎯 第 X 页处理完毕。新增入库 Y 个，跳过 Z 个。"
            match = re.search(r"新增入库 (\d+) 个", line)
            if match:
                page_inserted = int(match.group(1))
                
            # 安全熔断：如果 boss 已经没有数据了，防止死循环
            if "无数据返回，可能已到底部" in line:
                hit_bottom = True
                
        process.wait() # 等待本页脚本彻底结束
        
        # 累加本页成功入库的数量
        total_inserted += page_inserted
        
        if hit_bottom:
            print(f"\n>> ⚠️ 触发熔断：Boss直聘已无更多【{keyword}】相关数据。")
            break
            
        if total_inserted >= target_jobs:
            print(f"\n>> 🎉 目标达成！累计已成功入库 {total_inserted} 个岗位 (目标: {target_jobs})。程序停止下钻。")
            break
            
        # 还没抓够，准备下一页休眠
        current_page += 1
        wait_time = random.randint(180, 300)
        countdown_sleep(wait_time)

    print(f"\n>> 本轮动态抓取指令已全部执行完毕。最终入库总数：{total_inserted}")

def main():
    print("------------------------------------------")
    print("BOSS直聘 动态目标调度大管家 已启动")
    print("你可以输入: '帮我抓取 广州 ai应用 15-20k，抓50个岗位，从第4页开始'")
    print("------------------------------------------")

    while True:
        try:
            user_input = input("\n请输入指令 (输入 q 退出): ").strip()
            if not user_input: continue
            if user_input.lower() == 'q': break
            
            intent = parse_intent(user_input)
            if not intent:
                print("!! 无法识别有效参数，请重试。")
                continue
                
            # 提取参数
            kw = intent.get("keyword")
            ct = intent.get("city", "")
            sl = intent.get("salary", "不限").upper()
            sp = int(intent.get("start_page", 1))
            tj = int(intent.get("target_jobs", 15)) # 默认为抓取 15 个（约等于一页）
            
            print(f">> 确认任务: 关键词={kw}, 城市={ct}, 薪资={sl}, 起始页={sp}, 目标入库数={tj}")
            
            run_task(kw, ct, sp, tj, sl)
            
        except KeyboardInterrupt:
            print("\n>> 用户中断，程序退出。")
            break
        except Exception as e:
            print(f"!! 运行异常: {e}")

if __name__ == "__main__":
    main()