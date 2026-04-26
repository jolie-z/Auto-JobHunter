#!/usr/bin/env python3
"""
前程无忧 (51job) 全自动投递引擎 - 修复报错与物理点击版
"""

import os
import sys
import time
import json

# ==========================================
# 路径配置
# ==========================================
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "jobhunter-backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

try:
    import feishu_api
except ImportError:
    feishu_api = None
    print("⚠️ 警告：未检测到 feishu_api 模块，飞书状态同步功能将被禁用。")

from DrissionPage import ChromiumPage, ChromiumOptions

# ==========================================
# 全局常量
# ==========================================
TEMP_DIR = os.path.join(_PROJECT_ROOT, "temp_resumes")
COOKIE_FILE = os.path.join(_SCRIPT_DIR, '51job_cookies.json')
RESUME_CENTER_URL = "https://www.51job.com/resume/center?lang=c"

# ==========================================
# 浏览器初始化
# ==========================================
_co = ChromiumOptions()
page = ChromiumPage(_co)


def _inject_cookies_if_needed():
    """读取本地 51job cookie 文件并注入"""
    if os.path.exists(COOKIE_FILE):
        print("   🍪 注入 51job 登录态...")
        with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        page.get("https://www.51job.com/")
        page.set.cookies(cookies)
        page.refresh()
        time.sleep(2)


def _wait_for_resume_audit(timeout_mins=10):
    """轮询检测“审核中”标签是否消失"""
    print(f"   ⏳ 监控简历审核状态（限时 {timeout_mins} 分钟）...")
    start_time = time.time()
    while True:
        page.refresh()
        time.sleep(3)
        
        # 修复报错点：使用正确的 DrissionPage 文本模糊匹配语法
        audit_tag = page.ele('text=审核中', timeout=2)
        
        if audit_tag:
            elapsed = int(time.time() - start_time)
            if elapsed > timeout_mins * 60:
                print("   ❌ 简历审核超时。")
                return False
            print(f"   🕒 审核中... 已等待 {elapsed}s，30秒后刷新...")
            time.sleep(30)
        else:
            print("   ✅ 审核通过，简历已转正。")
            return True


def _manage_and_upload_resume(local_pdf_path: str, pdf_name: str):
    """简历中心管理：清理旧附件 -> 穿透上传 -> 状态校验"""
    print("   1. 访问 51job 简历中心...")
    page.get(RESUME_CENTER_URL)
    time.sleep(4) 

    # ---------------------------------------------------------
    # 步骤 A: 删除旧附件简历 (采用解法 3：可见父级过滤 + 原生JS击穿)
    # ---------------------------------------------------------
    more_btn = page.ele('css:.moreIcon', timeout=3)
    if more_btn:
        print("   🧹 准备清理旧简历...")
        more_btn.click(by_js=True)
        time.sleep(1)
        
        del_opt = page.ele('text:删除', timeout=2)
        if del_opt:
            del_opt.click(by_js=True)
            print("   🖱️ 已触发删除弹窗，启动解法 3 过滤隐藏 DOM...")
            time.sleep(1.5) # 给弹窗动画留出绝对充足的时间
            
            # ====== 👇 解法 3 核心代码 👇 ======
            # 策略 1：通过 CSS 找没有隐藏的 el-message-box__wrapper
            css_selector = 'css:.el-message-box__wrapper:not([style*="display: none"]) .el-message-box__btns .el-button--primary'
            confirm_del = page.ele(css_selector, timeout=2)
            
            if confirm_del:
                try:
                    confirm_del.click()
                    print("   ✅ 旧简历删除确认成功！(CSS过滤物理点击)")
                    time.sleep(2)
                except:
                    confirm_del.click(by_js=True)
                    print("   ✅ 旧简历删除确认成功！(CSS过滤JS点击)")
                    time.sleep(2)
            else:
                print("   ⚠️ DrissionPage 元素定位失效，启动原生 JS 暴力击穿...")
                
                # 策略 2：终极底牌，直接在当前网页的 Console 里执行原生 JS
                js_code = """
                let btns = document.querySelectorAll('.el-message-box__btns button');
                for(let i = 0; i < btns.length; i++) {
                    // 只要文字包含确定，并且 offsetParent 不为 null (代表在屏幕上是可见的)
                    if(btns[i].innerText.includes('确定') && btns[i].offsetParent !== null) {
                        btns[i].click();
                        return true;
                    }
                }
                return false;
                """
                js_result = page.run_js(js_code)
                
                if js_result:
                    print("   ✅ 旧简历删除确认成功！(原生 JS 暴力击穿)")
                    time.sleep(2)
                else:
                    print("   ❌ 所有破解方案均告失败，请手动检查 51job 页面弹窗结构。")
            # ====== 👆 解法 3 核心代码 👆 ======
            
    else:
        print("   ℹ️ 未检测到历史附件，跳过删除。")

    # ---------------------------------------------------------
    # 步骤 B: 唤起弹窗并上传
    # ---------------------------------------------------------
    abs_path = os.path.abspath(local_pdf_path)
    
    initial_btn = page.ele('css:.upload_btn.mb8', timeout=3)
    if not initial_btn:
        initial_btn = page.ele('text=上传附件简历', timeout=2)
    
    if initial_btn:
        initial_btn.click(by_js=True)
        time.sleep(2)

    page.set.upload_files(abs_path)
    modal_upload_trigger = page.ele('css:.uploadBox_btn', timeout=5)
    if modal_upload_trigger:
        modal_upload_trigger.click(by_js=True)
        print(f"   ⏳ 正在上传专属简历: {pdf_name}.pdf")
        time.sleep(3) 

    # ---------------------------------------------------------
    # 步骤 C: 确认添加 (彻底修复 NoRectError 幽灵DOM假死)
    # ---------------------------------------------------------
    print("   🖱️ 正在寻找并点击「确认添加」按钮...")
    clicked_confirm = False
    
    # 遍历页面上所有带“确认添加”字样的元素
    for btn in page.eles('text=确认添加', timeout=5):
        if btn.states.is_displayed:  # 核心：只抓取真正在屏幕上显示的那一个
            try:
                # Element UI 的文字通常包在 span 里，这里保险起见获取它的父节点 button
                target_btn = btn.parent('tag:button') if btn.tag == 'span' else btn
                target_btn.click(by_js=True) # 使用 JS 强制点击可见元素，最稳妥
                print("   ✅ 简历上传提交成功。")
                clicked_confirm = True
                time.sleep(2)
                break
            except Exception as e:
                print(f"   ⚠️ 尝试点击按钮时出现小插曲，继续寻找下一个... ({e})")
                
    if not clicked_confirm:
        # 如果还没找到，尝试备选方案
        fallback_btn = page.ele('css:.el-message-box__wrapper:not([style*="display: none"]) .el-button--primary', timeout=2)
        if fallback_btn and fallback_btn.states.is_displayed:
            fallback_btn.click(by_js=True)
            print("   ✅ 简历上传提交成功。(备选方案生效)")
        else:
            raise RuntimeError("❌ 未找到处于可见状态的「确认添加」按钮，上传失败。")

    # ---------------------------------------------------------
    # 步骤 D: 轮询审核状态
    # ---------------------------------------------------------
    return _wait_for_resume_audit()


def _apply_job(job_url: str):
    """直达岗位详情页投递"""
    print(f"   2. 访问岗位页: {job_url}")
    page.get(job_url)
    time.sleep(3)

    apply_btn = page.ele('css:a.but_sq', timeout=5)
    if not apply_btn:
        apply_btn = page.ele('text=申请职位', timeout=2)

    if apply_btn:
        apply_btn.click(by_js=True)
        print("   🚀 【申请职位】投递成功！")
        return True
    return False


def deliver_job(job_data: dict) -> bool:
    """全链路投递大脑入口"""
    _inject_cookies_if_needed()

    job_url    = job_data.get("job_url", "")
    file_token = job_data.get("file_token", "")
    pdf_name   = job_data.get("pdf_name", "resume")
    record_id  = job_data.get("record_id", "")

    pdf_filename   = f"{pdf_name}.pdf"
    local_pdf_path = os.path.join(TEMP_DIR, pdf_filename)
    os.makedirs(TEMP_DIR, exist_ok=True)

    try:
        if feishu_api:
            if not feishu_api.download_feishu_file(file_token, local_pdf_path):
                return False
        else:
            print("⚠️ 未配置飞书 API，跳过从飞书下载简历的步骤。")
            # 如果没有本地简历，直接返回
            if not os.path.exists(local_pdf_path):
                print("❌ 错误：缺少本地简历文件。")
                return False

        if _manage_and_upload_resume(local_pdf_path, pdf_name):
            if _apply_job(job_url):
                if feishu_api:
                    feishu_api.update_feishu_record(record_id, {"跟进状态": "已投递"})
                return True
        return False

    except Exception as exc:
        print(f"❌ 投递中断: {exc}")
        if record_id and feishu_api:
            feishu_api.update_feishu_record(record_id, {"自动投递失败日志": str(exc)[:100]})
        return False
    finally:
        if os.path.exists(local_pdf_path):
            try: os.remove(local_pdf_path)
            except: pass


if __name__ == "__main__":
    test_pdf_path = os.path.join(TEMP_DIR, "test_resume.pdf")
    if not os.path.exists(test_pdf_path):
        os.makedirs(TEMP_DIR, exist_ok=True)
        with open(test_pdf_path, 'w') as f:
            f.write("This is a mock PDF file for testing 51job upload.")

    test_job_url = "https://jobs.51job.com/guangzhou/149811232.html"  
    
    print("🚀 开始单独测试 51job 投递链路...")
    try:
        _inject_cookies_if_needed()
        audit_pass = _manage_and_upload_resume(test_pdf_path, "test_resume")
        
        if audit_pass:
            _apply_job(test_job_url)
            print("🏁 测试完成！请去网页确认是否投递成功。")
            
    except Exception as e:
        import traceback
        print(f"❌ 运行过程中遇到报错: {e}")
        traceback.print_exc()