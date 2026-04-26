#!/usr/bin/env python3
"""
猎聘网全自动投递引擎 (终极稳定版)

核心能力：
  1. Cookie 自动注入：无需手动接管浏览器，自动读取 liepin_cookies.json 恢复登录态。
  2. 飞书对接：动态拉取生成的专属 PDF 简历并下载到本地临时目录。
  3. 槽位突破：绕过猎聘 3 份附件简历上限，自动识别并清理旧的非通用版简历。
  4. 幽灵 DOM 穿透：无视前端干扰弹窗，精确定位隐藏的 <input> 实现静默秒传。
  5. 自动化沟通：直达岗位页，触发“聊一聊”，发送定制化开场白并推送专属附件简历。
  6. 状态回传：将投递结果实时写回飞书多维表格，并清理本地无用文件。
"""

import os
import sys
import time
import json
from datetime import datetime

# ==========================================
# 路径配置
# ==========================================
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
# 🌟 修复：直接将项目根目录加入环境变量
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    # 🌟 修复：精准导入最新的 common/feishu_api.py
    from common import feishu_api
except ImportError:
    feishu_api = None
    print("⚠️ 警告：未检测到 feishu_api 模块，飞书状态同步功能将被禁用。")

from DrissionPage import ChromiumPage, ChromiumOptions

# ==========================================
# 全局常量
# ==========================================
TEMP_DIR = os.path.join(_PROJECT_ROOT, "temp_resumes")
COOKIE_FILE = os.path.join(_SCRIPT_DIR, 'liepin_cookies.json') # 🌟 新增：Cookie文件路径
LIEPIN_HOME_URL = "https://c.liepin.com/"
LIEPIN_MAX_RESUMES = 3

# ==========================================
# 浏览器初始化
# ==========================================
_co = ChromiumOptions()
# 去掉端口限制，让 DrissionPage 自由启动浏览器
page = ChromiumPage(_co)


def _inject_cookies_if_needed():
    """读取本地 cookie 文件并注入到浏览器，实现免密登录"""
    if os.path.exists(COOKIE_FILE):
        print("   🍪 发现本地 Cookie 文件，正在注入登录态...")
        with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        
        # 必须先访问该域名，才能种下该域名的 Cookie
        page.get("https://www.liepin.com/")
        time.sleep(1)
        
        # DrissionPage 支持直接导入 Playwright 格式的 Cookie 列表
        page.set.cookies(cookies)
        page.refresh()
        time.sleep(2)
        print("   ✅ 登录态注入成功！")
    else:
        print("   ⚠️ 未找到 liepin_cookies.json，可能会跳转到登录页。请先运行 cookie_harvester.py")


def _clear_interfering_modals():
    """检测并关闭干扰弹窗（如“内容未保存”提示）"""
    for modal in page.eles("css:.ant-modal-content"):
        if modal.states.is_displayed:
            text = modal.text
            if "内容未保存" in text or "确定退出编辑" in text:
                print("   🧹 清理干扰弹窗：内容未保存提示")
                confirm_btn = modal.ele("text:确 定", timeout=2)
                if confirm_btn:
                    confirm_btn.click()
                    time.sleep(1)


def _handle_resume_sync_modals():
    """专门处理进入简历页时，猎聘询问是否【更新/同步在线简历】的各类干扰弹窗"""
    
    # 🌟 变体 1：拦截"X段经历可同步至在线简历中"弹窗（点击右上角 X）
    sync_title = page.ele('text:经历可同步至在线简历中', timeout=2)
    if sync_title:
        print("   🧹 拦截到【经历同步】弹窗，正在点击右上角「X」关闭...")
        # 定位 Ant Design 默认的右上角关闭按钮
        close_btn = page.ele('css:.ant-modal-close', timeout=2)
        if close_btn:
            close_btn.click(by_js=True)
            time.sleep(1.5)

    # 🌟 变体 2：拦截原来的二连环弹窗（点击"退出" -> 选原因 -> 确定）
    exit_btn = page.ele('text:退出', timeout=2)
    if exit_btn and exit_btn.states.is_displayed:
        print("   🧹 拦截到【是否更新在线简历】弹窗，正在点击「退出同步」...")
        exit_btn.click(by_js=True)
        time.sleep(2)

        reason_label = page.ele('tag:label', timeout=3)
        if not reason_label:
            reason_label = page.ele('css:[type="radio"]', timeout=1)

        if reason_label:
            print("   🧹 拦截到【为何不更新】追问弹窗，正在自动勾选原因...")
            reason_label.click(by_js=True)
            time.sleep(1)

            confirm_btn = page.ele('text:确 定', timeout=2)
            if not confirm_btn:
                confirm_btn = page.ele('text:确定', timeout=1)
            if not confirm_btn:
                confirm_btn = page.ele('text:提交', timeout=1)

            if confirm_btn:
                confirm_btn.click(by_js=True)
                print("   ✅ 成功击破简历同步二连环弹窗！")
                time.sleep(2)


def _manage_and_upload_resume(local_pdf_path: str, pdf_name: str):
    """访问首页 -> 精准进入附件简历页 -> 清理旧简历 -> 上传新简历"""
    print("   1. 正在访问猎聘首页...")
    page.get(LIEPIN_HOME_URL)
    time.sleep(3)

    entry_btn = page.ele('css:a[data-nick="aside-vap-bottom-btn0"]', timeout=5)
    if not entry_btn:
        print("   ⚠️ 首页快捷入口未找到，尝试直接跳转管理 URL...")
        page.get("https://c.liepin.com/resume/edit?showNPS=false")
    else:
        print("   ✅ 正在通过侧边栏进入【附件简历】...")
        entry_btn.click()
    
    time.sleep(4)
    _handle_resume_sync_modals()
    _clear_interfering_modals()

    try:
        title_ele = page.ele('text:附件简历', timeout=2)
        if title_ele:
            title_ele.scroll.to_see()
        else:
            page.scroll.down(500)
    except Exception:
        page.scroll.down(500)
    time.sleep(1)

    resume_items = page.eles("css:.resume-card-container")
    count_before = len(resume_items)
    print(f"   当前附件简历数量：{count_before}")

    if count_before >= LIEPIN_MAX_RESUMES:
        print(f"   ⚠️ 已达上限 ({LIEPIN_MAX_RESUMES} 份)，开始执行清理程序...")
        _delete_oldest_resume(resume_items)
        time.sleep(2)
        
        resume_items_after = page.eles("css:.resume-card-container")
        if len(resume_items_after) >= count_before:
            print("   ❌ 简历删除校验失败，尝试清理干扰弹窗后重试...")
            _clear_interfering_modals()
            _delete_oldest_resume(page.eles("css:.resume-card-container"))

    _upload_attachment_resume(local_pdf_path, pdf_name)


def _delete_oldest_resume(resume_items):
    """智能寻找非通用版简历进行删除清理"""
    target_item = None
    for item in reversed(resume_items):
        file_name_ele = item.ele("css:.file-name", timeout=1)
        file_name = file_name_ele.text if file_name_ele else ""
        if "通用版" not in file_name:
            target_item = item
            print(f"   🎯 锁定待删除目标: {file_name}")
            break

    if not target_item:
        print("   ⚠️ 未找到非通用版简历，安全降级：删除最后一份。")
        target_item = resume_items[-1]

    more_btn = target_item.ele("css:.more-icon", timeout=3)
    if not more_btn: return
    more_btn.click()
    time.sleep(1)

    clicked_del = False
    for menu in page.eles("css:.ant-dropdown-menu"):
        if menu.states.is_displayed:
            del_btn = menu.ele("xpath:.//*[contains(text(), '删除')]", timeout=2)
            if del_btn:
                del_btn.click()
                clicked_del = True
                break
    
    if not clicked_del:
        print("   ⚠️ 未在可见菜单中找到“删除”选项")
        return

    time.sleep(1.5)

    for modal in page.eles("css:.ant-modal-content"):
        if modal.states.is_displayed:
            content_text = modal.text
            if "不可恢复" in content_text or "确定要删除" in content_text:
                confirm = modal.ele("text:确 定", timeout=2)
                if confirm:
                    confirm.click()
                    print("   ✅ 已提交删除确认请求")
                    time.sleep(2)
                    return


def _upload_attachment_resume(local_pdf_path: str, pdf_name: str):
    """穿透 UI 弹窗静默上传核心逻辑"""
    abs_path = os.path.abspath(local_pdf_path)

    upload_btn = page.ele('css:[data-testid="attachment-resume-add-btn"]', timeout=5)
    if not upload_btn:
        upload_btn = page.ele('css:.resume-add-icon', timeout=2)

    if not upload_btn:
        raise RuntimeError("无法定位「+」号按钮，请核实页面是否处于附件简历区域")

    try:
        upload_btn.click(timeout=3)
    except Exception:
        upload_btn.click(by_js=True)

    if not page.wait.ele_displayed("css:.ant-upload-drag", timeout=5):
        print("   ⚠️ 弹窗未显示，触发 JS 强制重试...")
        upload_btn.click(by_js=True)
        page.wait.ele_displayed("css:.ant-upload-drag", timeout=5)

    drag_area = page.ele("css:.ant-upload-drag")
    file_input = drag_area.ele("tag:input", timeout=2)
    
    if not file_input:
        raise RuntimeError("弹窗内未找到文件输入控件")

    file_input.input(abs_path)
    print("   ⏳ 正在静默上传，请稍候...")
    
    # 🌟🌟🌟 新增：给前端2秒钟响应时间，等待恶心弹窗浮出，然后立刻调用清理助手 🌟🌟🌟
    import time
    time.sleep(2)
    _clear_liepin_annoying_popups(page)
    
    try:
        short_name = pdf_name[:8]
        # 🌟 稍微缩短一下这里的超时时间，因为前面的弹窗处理已经耗费了一点时间
        page.wait.ele_displayed(f"xpath://div[contains(@class, 'file-name') and contains(text(), '{short_name}')]", timeout=10)
        print(f"   ✅ 简历「{pdf_name}」上传成功并已渲染")
    except Exception:
        print(f"   ⚠️ 列表渲染超时，建议核实，流程继续。")

# ==========================================
# 🌟 猎聘防干扰弹窗清理助手
# ==========================================
def _clear_liepin_annoying_popups(page):
    """处理猎聘上传附件简历时的一连串恶心弹窗"""
    import random
    import time
    
    print("   🛡️ 启动防干扰弹窗清理机制...")
    
    # 🌟 新增：处理第二种新形态弹窗（解析成功后提示：X段经历可同步至在线简历中）
    new_sync_modal = page.ele('text:经历可同步至在线简历中', timeout=2)
    if new_sync_modal:
        print("   🔕 检测到新版【经历解析同步】弹窗，直接点击右上角「X」关闭...")
        # 优先寻找 Ant Design 的标准关闭按钮
        close_btn = page.ele('css:.ant-modal-close', timeout=2)
        if close_btn:
            close_btn.click(by_js=True)
        else:
            # 兜底查找任意含有 close 属性的关闭按钮
            fallback_close = page.ele('css:[class*="close"]', timeout=1)
            if fallback_close:
                fallback_close.click(by_js=True)
        time.sleep(1.5)
    
    # 1. 尝试点击第一层拒绝（如果它弹出了旧版的“是否同步到在线简历”）
    cancel_sync = page.ele('text:暂不同步', timeout=2) or page.ele('text:取消同步', timeout=1) or page.ele('text:不需要', timeout=1)
    if cancel_sync:
        print("   🔕 检测到【同步在线简历】弹窗，点击拒绝...")
        cancel_sync.click(by_js=True)
        time.sleep(1.5)

    # 2. 弹窗 1：处理“请问你退出的原因是”问卷
    reason_title = page.ele('text:请问你退出的原因是', timeout=2)
    if reason_title:
        print("   🔕 检测到【简历同步退出问卷】弹窗，正在随机选择原因...")
        try:
            # 随机选择前三个原因，避开最后一个
            options = ["解析效果不好", "在线简历中不想写太详细", "现在没时间确认，稍后同步"]
            choice = random.choice(options)
            option_ele = page.ele(f'text:{choice}', timeout=2)
            if option_ele:
                option_ele.click(by_js=True)
                time.sleep(0.5)

            # 点击【提交并退出】
            submit_btn = page.ele('text:提交并退出', timeout=2)
            if submit_btn:
                submit_btn.click(by_js=True)
                print("   ✅ 已点击【提交并退出】")
            else:
                # 兜底：点右上角的 X 退出
                close_btn = page.ele('css:.ant-modal-close', timeout=1)
                if close_btn: 
                    close_btn.click(by_js=True)
        except Exception as e:
            print(f"   ⚠️ 处理问卷弹窗失败: {e}")
        time.sleep(1.5)

    # 3. 弹窗 2：处理“退出同步”左上角二次确认
    exit_sync_btn = page.ele('text:退出同步', timeout=2)
    if exit_sync_btn:
        print("   🔕 检测到【二次确认退出同步】弹窗，正在点击退出...")
        try:
            exit_sync_btn.click(by_js=True)
            print("   ✅ 已成功彻底退出同步流程")
        except Exception as e:
            print(f"   ⚠️ 点击退出同步失败: {e}")
        time.sleep(1.5)
        print("   🔕 检测到【同步在线简历】弹窗，点击拒绝...")
        cancel_sync.click(by_js=True)
        time.sleep(1.5)

    # 2. 弹窗 1：处理“请问你退出的原因是”问卷
    reason_title = page.ele('text:请问你退出的原因是', timeout=2)
    if reason_title:
        print("   🔕 检测到【简历同步退出问卷】弹窗，正在随机选择原因...")
        try:
            # 随机选择前三个原因，避开最后一个
            options = ["解析效果不好", "在线简历中不想写太详细", "现在没时间确认，稍后同步"]
            choice = random.choice(options)
            option_ele = page.ele(f'text:{choice}', timeout=2)
            if option_ele:
                option_ele.click(by_js=True)
                time.sleep(0.5)

            # 点击【提交并退出】
            submit_btn = page.ele('text:提交并退出', timeout=2)
            if submit_btn:
                submit_btn.click(by_js=True)
                print("   ✅ 已点击【提交并退出】")
            else:
                # 兜底：点右上角的 X 退出
                close_btn = page.ele('css:.ant-modal-close', timeout=1)
                if close_btn: 
                    close_btn.click(by_js=True)
        except Exception as e:
            print(f"   ⚠️ 处理问卷弹窗失败: {e}")
        time.sleep(1.5)

    # 3. 弹窗 2：处理“退出同步”左上角二次确认
    exit_sync_btn = page.ele('text:退出同步', timeout=2)
    if exit_sync_btn:
        print("   🔕 检测到【二次确认退出同步】弹窗，正在点击退出...")
        try:
            exit_sync_btn.click(by_js=True)
            print("   ✅ 已成功彻底退出同步流程")
        except Exception as e:
            print(f"   ⚠️ 点击退出同步失败: {e}")
        time.sleep(1.5)

def _chat_and_send_resume(job_url: str, greeting: str, pdf_name: str):
    """直达岗位页 -> 打招呼 -> 发简历闭环"""
    page.get(job_url)
    time.sleep(3)

    # 1. 精准锁定沟通按钮
    chat_btn = page.ele('css:a[data-selector="chat-chat"]', timeout=5)
    if not chat_btn:
        chat_btn = page.ele("css:.btn-chat", timeout=2)

    if not chat_btn:
        raise RuntimeError(f"未找到「聊一聊/继续聊」按钮，可能岗位已下架，链接：{job_url}")

    # 2. 强行触发点击
    chat_btn.click(by_js=True)
    print("   点击沟通按钮，等待聊天框浮出...")

    # 验证聊天框是否弹出，若无则再补一枪
    is_chat_box_visible = page.wait.ele_displayed("css:.im-ui-chat-container", timeout=6)
    if not is_chat_box_visible:
        chat_btn.click(by_js=True)
        page.wait.ele_displayed("css:.im-ui-chat-container", timeout=4)

    input_box = page.ele("css:.im-ui-textarea", timeout=5)
    if not input_box:
        raise RuntimeError("未找到聊天输入框，聊天面板未能成功弹出")

    # 3. 强行聚焦并输入
    input_box.click(by_js=True)
    input_box.input(greeting)
    time.sleep(1)

    send_btn = page.ele("xpath://button/span[text()='发送']", timeout=5)
    if not send_btn:
        send_btn = page.ele("css:.im-ui-basic-send-btn", timeout=2)

    if not send_btn:
        raise RuntimeError("未找到聊天发送按钮")

    send_btn.click(by_js=True)
    time.sleep(2)
    print("   ✅ 定制打招呼语已发送")

    send_resume_btn = page.ele("css:.action-resume", timeout=5)
    if not send_resume_btn:
        raise RuntimeError("未找到聊天框顶部的「发简历」图标")

    send_resume_btn.click(by_js=True)
    time.sleep(2)

    # 调用精准选择简历模块
    _select_resume_in_modal(pdf_name)

    # 关键修复：点击新的"立即投递"按钮
    confirm_btn = page.ele("text:立即投递", timeout=5)
    if not confirm_btn:
        confirm_btn = page.ele("xpath://button[contains(., '立即投递')]", timeout=3)

    if not confirm_btn:
        print("   ⚠️ 警告：未找到「立即投递」确认按钮")
    else:
        confirm_btn.click(by_js=True)
        time.sleep(2)
        print("   ✅ 专属简历附件已成功投递！")


def _select_resume_in_modal(pdf_name: str):
    """在简历发送浮层中精确选中当前 PDF"""
    short_name = pdf_name[:8]

    # 等待浮层加载
    page.wait.ele_displayed("css:.ant-im-modal-body", timeout=5)

    # 关键修复：通过包裹文字的 p 标签，向上寻找到 label 容器进行点击
    target = page.ele(f"xpath://p[contains(text(), '{short_name}')]/ancestor::label", timeout=5)

    if not target:
        target = page.ele(f"text:{short_name}", timeout=3)

    if target:
        target.click(by_js=True)
        time.sleep(1)
        print(f"   ✅ 已选中目标简历: {short_name}...")
    else:
        print(f"   ⚠️ 未精确匹配到简历，默认发送系统第一位简历")


def deliver_job(job_data: dict) -> bool:
    """全链路执行引擎入口"""
    # 🌟 在全链路任务启动前，先检查并注入 Cookie
    _inject_cookies_if_needed()

    job_url    = job_data.get("job_url", "")
    file_token = job_data.get("file_token", "")
    pdf_name   = job_data.get("pdf_name", "resume")
    greeting   = job_data.get("greeting", "")
    record_id  = job_data.get("record_id", "")

    pdf_filename   = f"{pdf_name}.pdf"
    local_pdf_path = os.path.join(TEMP_DIR, pdf_filename)
    os.makedirs(TEMP_DIR, exist_ok=True)

    def _update_status(status: str):
        if record_id and feishu_api:
            update_fields = {"跟进状态": status}
            if status == "已投递":
                # 🌟 核心修复：飞书 API 要求日期必须是毫秒时间戳（int）
                import time
                current_ts = int(time.time() * 1000)
                update_fields["投递日期"] = current_ts
            feishu_api.update_feishu_record(record_id, update_fields)

    # 🌟 新增：专门记录投递失败日志，不改变跟进状态
    def _log_failure(error_msg: str):
        if record_id and feishu_api:
            feishu_api.update_feishu_record(record_id, {"自动投递失败日志": error_msg})

    try:
        if feishu_api:
            print(f"\n[{pdf_name}] ▶ A. 飞书数据联动 | 下载专属 PDF ...")
            ok = feishu_api.download_feishu_file(file_token, local_pdf_path)
            if not ok or not os.path.exists(local_pdf_path):
                _log_failure("简历下载失败")
                return False
            print(f"[{pdf_name}] ✅ PDF 准备就绪: {local_pdf_path}")
        else:
            print(f"⚠️ 未配置飞书 API，跳过从飞书下载简历的步骤。")
            if not os.path.exists(local_pdf_path):
                print(f"❌ 错误：缺少本地简历文件: {local_pdf_path}")
                return False

        print(f"[{pdf_name}] ▶ B. 突破限制 | 清理槽位与简历上传 ...")
        _manage_and_upload_resume(local_pdf_path, pdf_name)

        print(f"[{pdf_name}] ▶ C. 主动出击 | 发起沟通并投递附件 ...")
        _chat_and_send_resume(job_url, greeting, pdf_name)

        _update_status("已投递")
        print(f"[{pdf_name}] 🎉 本次全自动投递任务圆满结束！")
        return True

    except Exception as exc:
        err_msg = str(exc)[:100]
        print(f"[{pdf_name}] ❌ 投递异常中断：{err_msg}")
        _log_failure(f"投递异常中断: {err_msg}")
        return False

    finally:
        if os.path.exists(local_pdf_path):
            try:
                os.remove(local_pdf_path)
                print(f"[{pdf_name}] 🗑 本地缓存已安全擦除")
            except OSError as e:
                print(f"[{pdf_name}] ⚠️ 缓存擦除失败: {e}")


if __name__ == "__main__":
    # ==========================================
    # 局部测试 2：只测试 [沟通打招呼 + 发送附件简历] 
    # ==========================================
    
    # 🌟 在测试前，先检查并注入 Cookie
    _inject_cookies_if_needed()

    test_job_url = "https://www.liepin.com/job/1980507367.shtml" 
    
    test_greeting = """您好，我对贵司的AI应用落地岗非常感兴趣，我的过往经验与需求高度匹配。

我是一名兼具业务洞察力与技术交付能力的AI解决方案专家，专注于解决企业级场景中的实际痛点并推动规模化落地。

针对JD中"业务痛点挖掘与AI应用推进"的核心要求，我曾主导智能客服系统优化，通过语义识别模型将自助解决率提升至75%+，年降低转人工率15%；独立设计的库存预警系统将人工盘点耗时从3小时优化至秒级响应，实现零超卖运营。

附件为我的详细简历，期待能有机会与您进一步交流"""
    
    test_pdf_name = "测试专属简历"

    print("🚀 开始单独测试：沟通与投递模块...")
    print(f"🔗 目标岗位: {test_job_url}")
    print(f"📄 目标简历: {test_pdf_name}")
    
    try:
        _chat_and_send_resume(
            job_url=test_job_url,
            greeting=test_greeting,
            pdf_name=test_pdf_name
        )
        print("🏁 测试完成！请切回浏览器，确认是否成功发出了消息和简历。")
    except Exception as e:
        import traceback
        print(f"❌ 运行过程中遇到报错: {e}")
        traceback.print_exc()