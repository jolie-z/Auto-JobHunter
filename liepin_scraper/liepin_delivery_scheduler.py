#!/usr/bin/env python3
"""
投递任务调度大脑 (Dispatcher)
负责轮询飞书的待投递队列，并调度自动化引擎执行。
"""

import time
import random
import sys
import os

# 确保能引入 common 里的 feishu_api
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.join(_SCRIPT_DIR, "..")
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 🌟 修复：精准导入最新的 common/feishu_api.py
from common import feishu_api
import liepin_auto_delivery


def run_delivery_queue():
    print("🚀 启动全自动投递调度大脑...")

    # 启动前注入猎聘 Cookie
    liepin_auto_delivery._inject_cookies_if_needed()

    while True:
        print("\n📡 正在从飞书总表检索【待投递】的猎聘岗位...")

        # 拉取数据
        pending_jobs = feishu_api.get_jobs_to_deliver(target_platform="猎聘", target_status="待投递")

        if not pending_jobs:
            print("💤 暂无需要投递的岗位，休眠 1 分钟后再次检查...")
            time.sleep(60)
            continue

        print(f"🎯 发现 {len(pending_jobs)} 个待投递岗位，开始执行突击队列！")

        for idx, job in enumerate(pending_jobs):
            print(f"\n{'='*50}")
            print(f"▶️ 开始执行 [{idx+1}/{len(pending_jobs)}]：【{job['company']} - {job['job_title']}】")

            # 组装给投递引擎的数据结构
            job_data = {
                "record_id": job["record_id"],
                "job_url": job["job_url"],
                "file_token": job["file_token"],
                "pdf_name": job["pdf_name"],
                "greeting": job["greeting"]
            }

            # 调用底层猎聘投递引擎，执行全链路闭环
            if job.get("scheduled_at"):
                print("⏰ 检测到定时任务，预定时间已到，开始执行投递...")
            success = liepin_auto_delivery.deliver_job(job_data)

            if success:
                print(f"✅ 【{job['company']}】投递大获成功！")
            else:
                print(f"❌ 【{job['company']}】投递遇到障碍，状态已标记失败。")

            # 若不是最后一个岗位，执行防风控随机休眠
            if idx < len(pending_jobs) - 1:
                sleep_time = random.randint(60, 180)
                print(f"🛡️ 防风控保护：模拟真人操作，休眠 {sleep_time} 秒后继续处理下一个...")
                time.sleep(sleep_time)

        print("\n🎉 本轮投递队列执行完毕！重置进入轮询等待...")
        time.sleep(60)


if __name__ == "__main__":
    try:
        run_delivery_queue()
    except KeyboardInterrupt:
        print("\n🛑 调度器已被手动停止。")
