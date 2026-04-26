import subprocess
import time
import random
import csv
import io
import sqlite3
import os
import argparse
from datetime import datetime
import webbrowser

# 🌟 接入飞书 API 和详情抓取模块
from boss_detail_fetcher import fetch_job_detail

try:
    from common.feishu_api import get_active_search_configs
except ImportError:
    def get_active_search_configs():
        return []
    print("⚠️ 警告：未检测到 feishu_api 模块，飞书任务配置功能将被禁用。")

# ==========================================
# 核心路径配置
# ==========================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
DB_PATH = os.path.join(PARENT_DIR, 'data', 'job_hunter.db')

# 🌟 升级：支持自定义浏览器来源（chrome/edge/firefox），默认 edge
def refresh_edge_session():
    """强制唤醒 Edge 浏览器（即使它不是默认浏览器），维持登录状态，并强制同步最新 Cookie"""
    current_time = datetime.now().strftime('%H:%M:%S')
    print(f"      🔄 [{current_time}] 正在强制唤醒 Edge 浏览器刷新 Token...")
    
    url = "https://www.zhipin.com/"
    
    # 1. 跨平台【强制】打开 Edge 浏览器
    try:
        import platform
        sys_type = platform.system()
        
        if sys_type == "Darwin":  # macOS 系统
            # 使用 Mac 底层指令，强行拉起名为 "Microsoft Edge" 的应用
            subprocess.run(["open", "-a", "Microsoft Edge", url])
        elif sys_type == "Windows":  # Windows 系统
            # 使用 Win 底层指令，强行拉起 msedge 进程
            os.system(f"start msedge {url}")
        else:
            # Linux 环境下的后备方案
            import webbrowser
            webbrowser.open(url)
    except Exception as e:
        print(f"      ⚠️ 强行唤醒 Edge 失败: {e}")

    # 2. 加长等待时间！给防风控环境留出加载时间
    sleep_time = random.randint(12, 18)
    print(f"      ⏳ 正在等待浏览器加载防风控环境 ({sleep_time}秒)... 若有验证码请手动点击！")
    time.sleep(sleep_time)
    
    # 3. 跨平台模拟“物理机械臂” (真人鼠标动作)
    try:
        import pyautogui
        pyautogui.FAILSAFE = False 
        screen_width, screen_height = pyautogui.size()
        pyautogui.moveTo(screen_width / 2, screen_height / 2, duration=0.8)
        print("      🤖 [机械臂] 正在模拟真人滚动页面...")
        pyautogui.scroll(-800)
        time.sleep(1.2)
        pyautogui.scroll(500)
        time.sleep(2)
    except ImportError:
        print("      💡 提示: 未检测到 pyautogui。开源用户可运行 `pip install pyautogui` 解锁物理防风控。")
    except Exception as e:
        pass

    print("      ✅ 浏览器环境就绪，准备提取凭证...")

    # 4. 执行 Cookie 提取循环 (永远锁死 edge)
    for attempt in range(1, 4):
        print(f"      🔑 [第 {attempt}/3 次尝试] 正在将 Edge 的登录态同步至数据抓取引擎...")
        
        result = subprocess.run(
            ["boss", "login", "--cookie-source", "edge"], 
            capture_output=True, text=True
        )
        
        # 🌟 修复：合并 stdout 和 stderr，只要里面有成功字眼就放行
        combined_output = (result.stdout + result.stderr).lower()
        
        if "成功" in combined_output or "success" in combined_output or "cookies" in combined_output:
            print("      🎉 同步成功！引擎已获取最新通行证。")
            return True
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            if "凭证未通过" in error_msg:
                print("      ⚠️ 提取失败: 凭证未通过实际接口校验 (请确保 Edge 已登录 Boss)")
            else:
                print(f"      ⚠️ 提取失败: {error_msg[:100]}...")
            
            if attempt < 3:
                time.sleep(5)
            if "凭证未通过" in error_msg:
                print("      ⚠️ 提取失败: 凭证未通过实际接口校验 (可能风控弹窗未关，或 Cookie 已过期)")
            else:
                print(f"      ⚠️ 提取失败: {error_msg[:100]}...")
            
            if attempt < 3:
                time.sleep(5)
                
    print("      ❌ 连续 3 次同步失败。请确保你的 Edge 浏览器已登录 Boss 直聘！")
    return False

def check_job_exists(company_name, job_title, city):
    """前置去重检查"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 1 FROM raw_jobs 
            WHERE company_name = ? AND job_title = ? AND city = ?
        ''', (company_name, job_title, city))
        exists = cursor.fetchone() is not None
        return exists
    except Exception as e:
        print(f"      ❌ 数据库查询出错: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def save_single_job_to_db(job_data):
    """数据安全入库"""
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT OR IGNORE INTO raw_jobs (
                job_link, job_title, company_name, city, jd_text, 
                salary, work_address, hr_activity, industry, welfare_tags, 
                company_size, education_req, experience_req, hr_skill_tags, 
                company_intro, role, publish_date, platform, crawl_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_data.get('job_link', ''), job_data.get('job_title', ''),
            job_data.get('company_name', ''), job_data.get('city', ''),
            job_data.get('jd_text', ''), job_data.get('salary', ''),
            job_data.get('work_address', ''), job_data.get('hr_activity', ''),
            job_data.get('industry', ''), job_data.get('welfare_tags', ''),
            job_data.get('company_size', ''), job_data.get('education_req', ''),
            job_data.get('experience_req', ''), job_data.get('hr_skill_tags', ''),
            job_data.get('company_intro', ''), job_data.get('role', ''),          
            job_data.get('publish_date', ''), 'BOSS直聘', current_time                           
        ))
        inserted = cursor.rowcount > 0 
        conn.commit()
        return inserted
    except Exception as e:
        print(f"      ❌ 数据库写入出错: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def collect_single_page(keyword, city, salary, target_page):
    """
    🌟 核心改造：只执行指定的单页，不搞任何自动翻页
    """
    print(f"\n{'='*50}")
    
    # 🌟 将城市、关键词、薪资拼接成完整字符串，如果某个字段为空则自动忽略
    search_terms = [t for t in [city, keyword, salary] if t]
    full_query_str = "-".join(search_terms)
    
    print(f"📍 [手动翻页模式] 正在抓取【{full_query_str}】的第 {target_page} 页数据...")
    
    refresh_edge_session()
    
    # 强制只抓 15 个，并传递指定的页码 -p
    cmd = ["boss", "export", keyword, "-p", str(target_page), "-n", "15", "--format", "csv"]
    if city:
        cmd.extend(["--city", city])
    if salary:
        cmd.extend(["--salary", salary])

    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ 第 {target_page} 页列表抓取失败: {result.stderr}")
        return
        
    csv_content = result.stdout.strip()
    reader = csv.DictReader(io.StringIO(csv_content))
    jobs_list = list(reader)
    
    if not jobs_list:
        print(f"⚠️ 第 {target_page} 页无数据返回，可能已到底部。")
        return

    print(f"✅ 成功锁定本页的 {len(jobs_list)} 个岗位。")
    
    success_count = 0
    skip_count = 0
    
    for i, row in enumerate(jobs_list):
        security_id = row.get('securityId', row.get('\ufeffsecurityId', row.get('职位ID', '')))
        if not security_id: continue
            
        job_title = row.get('职位', row.get('职位名称', '未知岗位'))
        company_name = row.get('公司', row.get('公司名称', '未知公司'))
        current_city = row.get('地区', city)
        
        if check_job_exists(company_name, job_title, current_city):
            print(f"   ⏩ [拦截] [{i+1}/{len(jobs_list)}] {company_name} - {job_title} | 数据库已存在，跳过！")
            skip_count += 1
            continue
        
        print(f"   🔍 [{i+1}/{len(jobs_list)}] 正在抓取详情: {company_name} - {job_title}")
        
        # 详情下钻
        # 详情下钻
        full_desc, address, encrypt_id, extra_info = fetch_job_detail(
            security_id, on_captcha_callback=refresh_edge_session 
        )
        
        if not full_desc: continue
            
        job_data = {
            'job_link': f"https://www.zhipin.com/job_detail/{encrypt_id}.html",
            'job_title': job_title, 'company_name': company_name, 'city': current_city,
            'jd_text': full_desc, 'salary': row.get('薪资', ''), 'work_address': address,
            'hr_activity': extra_info.get("hr_active", ""), 'industry': extra_info.get("industry", ""),
            'welfare_tags': extra_info.get("welfare", ""), 'company_size': extra_info.get("scale", ""),
            'education_req': row.get('学历', extra_info.get("degree", "")),
            'experience_req': row.get('经验', extra_info.get("experience", "")),
            'hr_skill_tags': extra_info.get("hr_skills", ""), 'company_intro': '', 
            'role': '', 'publish_date': datetime.now().strftime("%Y-%m-%d"),
        }
        
        if save_single_job_to_db(job_data): success_count += 1
        
        # ⚠️ 必须保留的微观休眠：下钻动作之间的安全间隔
        time.sleep(random.randint(20, 35))
        
    print(f"🎯 第 {target_page} 页处理完毕。新增入库 {success_count} 个，跳过 {skip_count} 个。")

def start_auto_patrol(target_page, platform="boss", keyword=None, city=None, salary=None):
    """主控引擎：读取飞书任务，按平台和页码执行"""
    print(f"🚀 启动 [{platform}] 精准采集矩阵 | 当前锁定页码: P{target_page}")
    
    # 🌟 平台分支拦截逻辑
    if platform != "boss" and platform != "boss直聘":
        print(f"⚠️ 注意：[{platform}] 平台的底层爬虫协议还在开发中。")
        print(f"   本轮针对 {platform} 的第 {target_page} 页指令已模拟接收，直接跳过。")
        return

    # 🌟 如果调度器传入了明确的搜索条件，直接使用，不再读飞书配置表
    if keyword:
        print(f"🎯 使用调度器传入的搜索条件：keyword={keyword}, city={city}, salary={salary}")
        collect_single_page(keyword, city or '', salary or '', target_page)
        print("\n🏁 本次手动页面抓取指令已全部执行完毕！程序退出。")
        return

    search_tasks = get_active_search_configs()
    
    if not search_tasks:
        print("🤷‍♂️ 飞书中没有找到启用的任务！")
        return
    
    for i, task in enumerate(search_tasks):
        kw = task.get('keyword', '')
        ct = task.get('city', '')
        sl = task.get('salary', '')
        
        collect_single_page(kw, ct, sl, target_page)
        
        # 如果有多个飞书任务，任务之间歇息 3-5 分钟
        if i < len(search_tasks) - 1:
            print("💤 切换飞书搜索任务，短暂休眠避开风控...")
            time.sleep(random.randint(180, 300))
            
    print("\n🏁 本次手动页面抓取指令已全部执行完毕！程序退出。")

if __name__ == "__main__":
    # 🌟 接入 argparse 允许命令行传参
    parser = argparse.ArgumentParser(description="多平台半自动单页采集器")
    parser.add_argument('--platform', type=str, default='boss', help="指定目标平台")
    parser.add_argument('-p', '--page', type=int, default=1, help="指定要抓取的页码，默认是 1")
    parser.add_argument('--keyword', type=str, default=None, help="搜索关键词")
    parser.add_argument('--city', type=str, default=None, help="搜索城市")
    parser.add_argument('--salary', type=str, default=None, help="薪资范围")
    args = parser.parse_args()
    
    start_auto_patrol(args.page, args.platform, args.keyword, args.city, args.salary)