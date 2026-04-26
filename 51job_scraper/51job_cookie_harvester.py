#!/usr/bin/env python3
"""
51job（前程无忧）Cookie 采集器

功能：
1. 启动 Chromium 浏览器（非无头模式）
2. 使用 playwright_stealth 擦除自动化特征
3. 导航到 51job 登录页面
4. 等待用户手动扫码登录
5. 提取并保存 Cookie 到 51job_cookies.json
"""

import json
import os
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

def harvest_51job_cookies():
    """
    半自动化采集 51job 登录 Cookie
    """
    print("🚀 启动 51job Cookie 采集器...\n")
    
    try:
        # 步骤 1: 使用 Stealth v2.0+ 全局注入方式初始化 Playwright
        print("📦 正在初始化 Playwright（Stealth v2.0+ 全局注入）...")
        with Stealth().use_sync(sync_playwright()) as p:
            # 步骤 2: 启动 Chromium 浏览器（非无头模式）
            print("🌐 正在启动 Chromium 浏览器（可见模式）...")
            browser = p.chromium.launch(
                headless=False,  # 必须可见，方便手动登录
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            # 步骤 3: 创建浏览器上下文
            print("🔧 正在创建浏览器上下文...")
            context = browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            )
            
            # 步骤 4: 创建页面（Stealth 已全局注入，无需手动调用）
            print("🥷 Stealth 伪装已全局注入，自动擦除自动化特征...")
            page = context.new_page()
            
            # 步骤 5: 导航到 51job 登录页面
            print("🔗 正在导航到 51job 登录页面...")
            job51_url = "https://we.51job.com/"
            page.goto(job51_url, wait_until='domcontentloaded', timeout=30000)
            
            print("\n" + "="*70)
            print("⚠️  请在弹出的浏览器中手动完成扫码登录")
            print("⚠️  登录成功后，请回到此终端按下【回车键】继续...")
            print("="*70 + "\n")
            
            # 步骤 6: 阻塞等待用户手动登录
            input("👉 按下回车键继续... ")
            
            # 步骤 7: 提取 Cookie
            print("\n🍪 正在提取 Cookie...")
            cookies = context.cookies()
            
            if not cookies:
                print("⚠️  警告：未检测到任何 Cookie，可能登录未成功")
                print("提示：请确保已完成登录，然后重新运行此脚本")
                return
            
            print(f"✅ 成功提取 {len(cookies)} 个 Cookie")
            
            # 步骤 8: 保存 Cookie 到文件
            output_file = os.path.join(os.path.dirname(__file__), '51job_cookies.json')
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            
            print(f"💾 Cookie 已保存到: {output_file}")
            print("\n" + "="*70)
            print("🎉 Cookie 提取成功并已保存！")
            print("="*70)
            
            # 打印部分 Cookie 信息供验证
            print("\n📋 Cookie 预览（前 3 个）:")
            for i, cookie in enumerate(cookies[:3]):
                print(f"   {i+1}. {cookie.get('name', 'N/A')} = {cookie.get('value', 'N/A')[:20]}...")
            
            # 步骤 9: 清理资源（在 with 块内完成）
            print("\n🧹 正在清理资源...")
            browser.close()
            print("✅ 浏览器已关闭")
        
            
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断操作")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n👋 程序结束")

if __name__ == "__main__":
    harvest_51job_cookies()
