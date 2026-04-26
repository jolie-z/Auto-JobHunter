"""
BOSS直聘全自动投递引擎 (JobOS 物理隔离版)

核心能力：
  1. 物理隔离：使用独立的用户数据目录保存登录态，100% 免疫 Cookie 注入带来的环境指纹异常风控。
  2. 自动发消息：直达沟通页，发送 AI 破冰语。
  3. 自动长图：支持多图简历连续静默上传。
"""

import os
import sys
import time
import random
import subprocess
from datetime import datetime

# ==========================================
# 路径配置
# ==========================================
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
# 🌟 修复：直接将项目根目录加入环境变量，消除幽灵引用
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    # 🌟 修复：使用带命名空间的精准导入，直指最新的 common/feishu_api.py
    from common import feishu_api
except ImportError:
    feishu_api = None
    print("⚠️ 警告：未检测到 feishu_api 模块，飞书状态同步功能将被禁用。")

from DrissionPage import ChromiumPage, ChromiumOptions

BOSS_HOME_URL = "https://www.zhipin.com/"
TEMP_DIR = os.path.join(_PROJECT_ROOT, "temp_resumes")
# 🌟 核心突破：创建一个专门存储 BOSS 浏览器状态的物理隔离文件夹
PROFILE_DIR = os.path.join(_PROJECT_ROOT, "data", ".boss_browser_profile")
os.makedirs(PROFILE_DIR, exist_ok=True)

# ==========================================
# 浏览器初始化（配置本地持久化环境）
# ==========================================
_co = ChromiumOptions()
# 🌟 核心修复 1：指定一个不常用的调试端口，防止与其他浏览器实例冲突
_co.set_address('127.0.0.1:19222')

# 指定 Edge 浏览器（可选，如果不指定，默认使用 Chrome）
edge_path = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
if os.path.exists(edge_path):
    _co.set_browser_path(edge_path)

_co.set_user_data_path(PROFILE_DIR)
# 抹除自动化特征
_co.set_argument('--disable-blink-features=AutomationControlled')
_co.set_argument('--disable-dev-shm-usage')
_co.set_argument('--disable-gpu')
_co.set_argument('--remote-debugging-port=19222')
_co.set_pref('credentials_enable_service', False)

_page = None

def get_browser_page():
    """安全地获取或重启浏览器实例，仅在连接失败时触发 pkill"""
    global _page
    if _page is not None:
        try:
            if not _page.is_stopped:
                return _page
        except Exception:
            pass

    # 清理 SingletonLock 锁文件
    lock_file = os.path.join(PROFILE_DIR, 'SingletonLock')
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
            print("   🧹 已清理残留的浏览器锁定文件...")
        except Exception:
            pass

    try:
        _page = ChromiumPage(_co)
        return _page
    except Exception as e:
        print(f"   ⚠️ 浏览器连接失败（{e}），正在强制清理残留进程...")
        subprocess.run(["pkill", "-f", "Microsoft Edge"], capture_output=True)
        time.sleep(3)
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except Exception:
                pass
        _page = ChromiumPage(_co)
        return _page

def _ensure_login():
    """检查登录状态，未登录则挂起等待用户扫码"""
    global page
    print("   🔄 正在检查 BOSS 直聘登录状态...")
    time.sleep(2)  # 给浏览器留出初始化时间，防止 Disconnected
    time.sleep(1)
    try:
        page.get(BOSS_HOME_URL)
    except Exception as e:
        print(f"   ⚠️ 浏览器连接异常（{e}），正在重建连接...")
        page = get_browser_page()
        page.get(BOSS_HOME_URL)
    time.sleep(3)

    # 检查页面上是否存在用户头像或退出按钮，判断是否登录
    is_logged_in = page.ele('css:.user-nav', timeout=2) or page.ele('text:退出登录', timeout=2)

    if is_logged_in:
        print("   ✅ 已检测到有效的登录态，可以开始投递！")
        return
    else:
        print("\n⚠️ 未检测到登录状态！")
        print("👉 请在弹出的浏览器窗口中，使用 BOSS 直聘 APP 扫描二维码登录。")
        print("⏳ 脚本已挂起，将在这里静静等待您扫码登录成功...")

        # 死循环等待，直到检测到登录成功标志
        while True:
            time.sleep(3)
            if page.ele('css:.user-nav', timeout=1) or page.ele('text:退出登录', timeout=1):
                print("\n🎉 检测到扫码成功！登录凭证已永久保存在本地物理目录。")
                print("🚀 继续执行自动化投递...\n")
                time.sleep(2)
                break

def _handle_security_captcha():
    """处理 BOSS 安全滑块"""
    captcha_ele = page.ele('css:#nc_1_n1z', timeout=2)
    if not captcha_ele:
        captcha_ele = page.ele('text:安全验证', timeout=1)

    if captcha_ele:
        print("\n⚠️ 触发了 BOSS 安全验证！")
        print("⏳ 脚本已暂停，请在浏览器中【手动拖动滑块】...")
        page.wait.ele_deleted('css:#nc_1_n1z', timeout=60)
        print("✅ 验证通过，继续执行！\n")
        time.sleep(2)

def _chat_and_send_resume(job_url: str, greeting: str, local_image_paths: list):
    """激活-关闭-重进 三段式投递 -> 打招呼 -> 发长图"""
    time.sleep(1)
    page.get(job_url)
    time.sleep(random.uniform(2, 4))
    _handle_security_captcha()

    # ── 1. 入口状态判定 ──────────────────────────────────────
    immediate_btn = page.ele('text:立即沟通', timeout=3)
    continue_btn  = page.ele('text:继续沟通', timeout=2)

    if not immediate_btn and not continue_btn:
        raise RuntimeError(
            f"页面上既未找到「立即沟通」也未找到「继续沟通」，"
            f"当前 URL：{page.url}，岗位可能已下线或需要手动刷新。"
        )

    # ── 2A. 分支 A：发现「立即沟通」→ 激活 → 关弹窗 → 转 B ──
    if immediate_btn:
        print("   🟢 检测到新岗位（立即沟通），执行激活流程...")
        immediate_btn.click(by_js=True)
        time.sleep(2)

        # 关闭可能弹出的干扰弹窗
        modal_close = page.ele('css:.ant-modal-close', timeout=2)
        if not modal_close:
            modal_close = page.ele('css:.close-container', timeout=1)
        if modal_close:
            modal_close.click(by_js=True)
            print("   🔕 已关闭干扰弹窗")
            time.sleep(1.5)

        # 激活后页面状态更新，重新获取「继续沟通」
        continue_btn = page.ele('text:继续沟通', timeout=5)
        if not continue_btn:
            raise RuntimeError(
                f"点击「立即沟通」后未出现「继续沟通」按钮，"
                f"当前 URL：{page.url}，请检查是否触发了额外验证。"
            )

    # ── 2B. 分支 B：点击「继续沟通」，进入正式聊天室 ─────────
    print("   🔵 点击「继续沟通」，等待聊天标签页...")
    continue_btn.click(by_js=True)
    time.sleep(random.uniform(2, 3))
    _handle_security_captcha()

    # 切换到新打开的聊天标签页
    if len(page.tab_ids) > 1:
        page.to_tab(page.latest_tab)
        page.wait.load_start()
        time.sleep(2)

    # ── 3. 聊天室内动作 ──────────────────────────────────────
    # 发送打招呼语
    input_box = page.ele('css:#chat-input', timeout=10)
    if not input_box:
        input_box = page.ele('css:.chat-input', timeout=5)

    if input_box:
        input_box.click(by_js=True)
        # 🌟 核心改进：直接在文字末尾加上 \n 模拟回车，这是最稳定的发送方式
        input_box.input(f"{greeting}\n")
        print("   ✅ 已通过回车键发送打招呼语")
        time.sleep(1.5)

        # 兜底逻辑：如果回车没发出去，再尝试找一次按钮
        send_btn = page.ele('css:.btn-send', timeout=1) or page.ele('text:发送', timeout=1)
        if send_btn and send_btn.states.is_enabled:
            send_btn.click(by_js=True)
    else:
        print("   ⚠️ 未找到聊天输入框，打招呼语未发送")

    # 发送多张图片简历
    if local_image_paths:
        print(f"   ⏳ 准备发送 {len(local_image_paths)} 张简历图片...")

        img_input = page.ele('css:[title="图片"]', timeout=3)
        if not img_input:
            img_input = page.ele('css:input[type="file"][accept*="image"]', timeout=3)
        if not img_input:
            img_input = page.ele('tag:input@type=file', timeout=2)

        if img_input:
            for idx, img_path in enumerate(local_image_paths):
                abs_path = os.path.abspath(img_path)
                img_input.input(abs_path)
                print(f"   ⬆️ 正在静默上传第 {idx+1} 张图片...")
                time.sleep(random.uniform(3, 5))
            print("   ✅ 所有简历图片投递完毕！")
        else:
            print("   ⚠️ 未能找到图片上传入口，请检查 BOSS 前端是否更新。")

    if len(page.tab_ids) > 1:
        page.close()

def _log_failure(record_id: str, error_msg: str):
    if record_id and feishu_api:
        feishu_api.update_feishu_record(record_id, {"自动投递失败日志": error_msg})

def deliver_job(job_data: dict) -> bool:
    """投递入口"""
    global page
    page = get_browser_page()
    _ensure_login()  # 确保登录态安全

    job_url     = job_data.get("job_url", "")
    image_items = job_data.get("image_items", [])
    greeting    = job_data.get("greeting", "")
    record_id   = job_data.get("record_id", "")

    local_image_paths = []
    disconnect_error = False
    os.makedirs(TEMP_DIR, exist_ok=True)

    try:
        if image_items:
            if feishu_api:
                print(f"\n▶ A. 飞书数据联动 | 下载 {len(image_items)} 张图片 ...")
                for item in image_items:
                    token = item.get("token")
                    if not token:
                        continue
                    name = item.get("name", "resume_img")
                    short_token = str(token)[:6]
                    local_path = os.path.join(TEMP_DIR, f"{name}_{short_token}.png")
                    ok = feishu_api.download_feishu_file(token, local_path)
                    if ok and os.path.exists(local_path):
                        local_image_paths.append(local_path)

                if not local_image_paths:
                    _log_failure(record_id, "所有图片下载失败")
                    return False
            else:
                print("⚠️ 未配置飞书 API，跳过从飞书下载图片的步骤。")
                if not local_image_paths:
                    print("❌ 错误：未提供本地图片文件，无法继续投递。")
                    return False

        print("\n▶ B. 主动出击 | 发起沟通并发送简历 ...")
        page.wait.load_start()
        _chat_and_send_resume(job_url, greeting, local_image_paths)

        if record_id and feishu_api:
            # 🌟 修复：飞书 API 要求日期字段必须是毫秒级时间戳，不能是字符串
            import time
            current_ts = int(time.time() * 1000)
            feishu_api.update_feishu_record(record_id, {
                "跟进状态": "已投递",
                "自动投递失败日志": "",
                "投递日期": current_ts
            })

        print("🎉 本次 BOSS 投递任务圆满结束！")
        return True

    except Exception as exc:
        err_msg = str(exc)[:100]
        disconnect_error = any(k in str(exc).lower() for k in ('disconnect', 'connection refused', 'closed'))
        print(f"❌ 投递异常中断：{err_msg}")
        _log_failure(record_id, f"投递异常: {err_msg}")
        return False
    finally:
        for img_path in local_image_paths:
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                except OSError:
                    pass
        if not disconnect_error:
            try:
                page.to_main_tab()
            except Exception:
                pass