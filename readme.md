
# 🚀 Auto-Job-Hunter | 全自动 AI 求职

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![License: Custom](https://img.shields.io/badge/License-Custom_NonCommercial-red.svg)](#-版权声明-license)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

Auto-Job-Hunter 是一个工业级的多平台全自动求职系统。它不仅仅是一个爬虫，而是一个集成了 **DOM 穿透抓取、多智能体(Multi-Agent)简历重写、一票否决规则树、以及飞书云端大盘** 的硬核求职矩阵。

支持平台：**BOSS 直聘** | **前程无忧 (51job)** | **猎聘网**

---

## ✨ 核心特性 (Features)

* 🕷️ **多平台制霸与防风控**
  * 采用 Playwright Stealth v2.0+ 抹除 WebDriver 特征。
  * 独创 **“影帝级”鼠标轨迹伪装** 与物理隔离 Profile 目录，无视常规检测。
  * 猎聘/51job DOM 穿透：无视前端干扰弹窗，精确静默秒传附件。
* 🧠 **LangGraph 多智能体协作**
  * 告别单次大模型调用的敷衍。采用 `Splitter -> Architect -> Critic -> Formatter` 四阶段 Agent 工作流。
  * 独创 **80 分放行机制**，打分不合格自动打回重写，确保发给 HR 的每一句话都是王炸。
* 🛡️ **双漏斗清洗过滤引擎 (Veto System)**
  * **硬规则清洗**：自定义 JSON 词库，遇“外包、管培、销售、单休”直接一票否决，坚决不浪费 AI Token。
  * **LLM 深度体检**：提取 JD 潜台词，生成“高杠杆匹配点”与“致命硬伤与毒点”报告。
* 📊 **云端与本地数据双向奔赴**
  * 采用 **SQLite WAL 模式**，支持多进程高并发抓取不锁表。
  * **飞书多维表格 (Bitable)** 双向同步：在手机上用飞书看 AI 汇总的岗位大盘，随时掌控求职进度。
* 💻 **极客范 Next.js 控制台**
  * SSE (Server-Sent Events) 实时通讯，在网页端弹出的“悬浮终端”中，像黑客一样看着爬虫日志流式输出。

---

## 🏗️ 架构全景 (Architecture)

```text
抓取 (Scrape) ➡️ 入库 (SQLite) ➡️ 规则清洗 (Rule Filter) ➡️ 云端看板 (Feishu) ➡️ 深度评估 (LLM Agent) ➡️ 自动投递 (Auto Delivery)
```

---

## 🛠️ 快速开始 (Quick Start)

### 1. 硬件与系统前置要求 ⚠️ (必看)
* **操作系统**：当前代码高度定制化，**建议在 macOS 环境下运行**（底层强依赖 Mac 的 `osascript` 唤醒浏览器机制及 Mac 版 Word 的 PDF 转换引擎）。Windows/Linux 用户需自行修改底层的脚本执行逻辑。
* **Python**：**3.10 及以上版本**（代码中使用了 `X | Y` 等较新的语法特性）。
* **Node.js**：**18+**（并全局安装 `pnpm` 包管理器）。
* **系统依赖**：必须通过 Homebrew 安装 `poppler`（PDF 转长图引擎的 C++ 底层依赖）。
* **账号与秘钥**：准备好 OpenAI 格式的大模型 API Key，以及一个飞书账号。

### 2. 基础环境搭建
打开 Mac 终端，按顺序执行以下命令：

```bash
# 1. 安装系统级依赖
brew install poppler

# 2. 克隆项目
git clone [https://github.com/](https://github.com/)[你的用户名]/Auto-Job-Hunter-OpenSource.git
cd Auto-Job-Hunter-OpenSource

# 3. 配置 Python 虚拟环境 (强烈推荐)
python3 -m venv venv
source venv/bin/activate

# 4. 安装 Python 全家桶依赖
pip install -r requirements.txt

# 5. 下载 Playwright 浏览器专属内核 (必须执行)
playwright install chromium
```

### 3. 初始化极客控制台 (前端)
由于前端使用了锁版本的 `pnpm-lock.yaml`，请务必使用 `pnpm` 安装：
```bash
# 如果你没有 pnpm，先全局安装：npm install -g pnpm
cd frontend
pnpm install
cd ..
```

### 4. 授权 Mac 辅助功能 (防报错关键)
由于脚本使用了 `pyautogui` 模拟真实的物理鼠标轨迹：
* 请打开 Mac 的 **「系统设置」 -> 「隐私与安全性」 -> 「辅助功能」**。
* 将你的 **终端应用 (Terminal / iTerm2)** 以及 **IDE (VSCode / Cursor / PyCharm)** 添加进去并开启开关，否则运行时会报权限错误。

### 5. 配置文件与基础设施
复制环境模板并填入你的密钥：
```bash
cp common/config_example.py common/config.py
cp .env.example .env
```
*(请在 `.env` 中填入你的 `OPENAI_API_KEY`，飞书相关的 Key 将在下一步获取)*

### 6. 📊 飞书多维表格 (Bitable) 数据库配置指南
本项目使用“飞书多维表格”作为轻量级的云端数据库和极客控制面板。为了让程序能够读写你的飞书表格，请严格按照以下步骤配置：

#### 6.1 克隆数据库模板
1. 打开模板：访问 👉 **[Auto-Job-Hunter 求职自动化模板](https://ucncdzmaddi9.feishu.cn/base/J3Y2bWGqta395LsIOZyctit6nlh?from=from_copylink)**（**访问密码**：`9&8T6388`）。
2. 转存模板：点击页面右上角的 “使用该模板” 或 “复制”。
3. 确认转存：将其保存到你的“我的空间”中。接下来的所有 ID 获取操作，都请在你自己空间下的这份新表格中进行。

#### 6.2 获取开发者凭证与终极授权 (APP_ID & APP_SECRET)
1. **登录平台**：访问 [飞书开放平台](https://open.feishu.cn/app/) 并登录。
2. **创建应用**：点击 **“创建企业自建应用”**，为应用起名（例如：`Auto-Job-Hunter`），点击创建。
3. **获取密钥**：在左侧栏 **“凭证与基础信息”** 中复制 `App ID` 和 `App Secret`，填入 `.env` 文件。
4. 🤖 **添加机器人实体（必做！）**：在左侧栏 **“应用功能” -> “添加应用能力”** 中，找到 **“机器人”** 并点击添加。*(注：只有赋予了机器人能力，你的代码才能拥有一个“身份”去编辑文档)*。
5. **开通数据权限**：在左侧栏 **“开发配置” -> “权限管理”**，开通以下两个核心权限：
   * `查看、评论、编辑和管理多维表格` (bitable:app:read_write)
   * `查看、评论和导出多维表格` (bitable:app:readonly)
6. **发布应用**：在左侧栏 **“应用发布” -> “版本管理与发布”**，创建版本（如 `1.0.0`）并申请发布。
7. 🔑 **给机器人“发钥匙”（极其重要！防 403 报错指南）**：
   * 回到你转存的**飞书多维表格**页面，点击右上角 **“分享”** 或 **“添加协作者”**（带 `+` 号的小人图标）。
   * 在搜索框中搜索你创建的应用名称（如 `Auto-Job-Hunter`），授予其 **“可编辑”** 权限并完成。
   * 💡 **【进阶避坑 Workaround】**：如果系统抽风，**在协作者搜索框里搜不到你的应用**，请使用以下“曲线救国”绝招：
     1. 打开飞书客户端，发起一个群聊，把你本人和刚才创建的机器人拉进同一个群。
     2. 将你的多维表格链接直接发送到这个群聊中。
     3. 在表格的分享面板中，将权限设置为**“获得链接的群成员均可编辑”**。这样机器人就能顺理成章地获得数据写入权限了！

#### 6.3 获取数据库坐标 (APP_TOKEN & TABLE_ID)
观察转存后的飞书多维表格浏览器网址：
`https://你的域名.feishu.cn/base/xxxxxxxxxxxxxx?table=yyyyyyyyyy&view=...`

1. **获取 APP_TOKEN（Base ID）**：
   * **标准模式**：网址包含 `/base/`，App Token 是 `/base/` 后面、`?` 之前的一串字符。*(填入 `.env` 的 `FEISHU_APP_TOKEN`)*
   * **Wiki 模式**：若网址以 `/wiki/` 开头，请去 [飞书 API 调试台](https://open.feishu.cn/api-explorer/) -> “知识库” -> “获取节点信息 (get_node)”，传入 wiki 链接里的代码获取真实的 `obj_token`，填入 `.env`。
2. **获取五个关键 TABLE_ID**：
   点击表格底部的标签页，每切换一个表，网址中 `table=` 后面的 ID 就会改变。请依次复制并填入 `.env`：
   * 岗位表 ➡️ `FEISHU_TABLE_ID_JOBS`
   * 配置表 ➡️ `FEISHU_TABLE_ID_CONFIG`
   * 提示词表 ➡️ `FEISHU_TABLE_ID_PROMPTS`
   * 简历表 ➡️ `FEISHU_TABLE_ID_RESUMES`
   * 偏好表 ➡️ `FEISHU_TABLE_ID_PREFERENCES`

### 7. 初始化本地 SQLite 数据底座
```bash
python data/db_manager.py
# 看到 "✅ 数据库初始化成功！WAL 模式已激活" 即可
```

---

## 🚀 运行系统 (Usage)

系统采用“先物理授权，后逻辑调度”的防风控模式，请按以下流水线操作：

### 阶段一：采集身份令牌 (Cookie Harvesting)
首次运行，需让系统获取各大平台的通行证（本地缓存，绝不上云）。

* **BOSS 直聘**：
  ```bash
  python boss_scraper/boss login --cookie-source edge
  # 按提示打开 Edge 登录 Boss 直聘网页版，终端显示“✅ 登录成功”即可。
  ```
  
* **猎聘网**：
  ```bash
  python liepin_scraper/liepin_cookie_harvester.py
  ```
* **前程无忧 (51job)**：
  ```bash
  python 51job_scraper/51job_cookie_harvester.py
  ```
*(💡 运行后系统会弹出浏览器，请手动完成扫码登录，看到成功提示后关闭浏览器即可。有效期内无需重复获取。)*

### 阶段二：启动控制台基础服务
新开两个终端窗口，分别运行后台引擎与极客控制台：
```bash
# 终端 1：启动 FastAPI 后端大脑
cd jobhunter-backend
python main.py

# 终端 2：启动 Next.js 沉浸式工作台
cd frontend
pnpm dev or npm run dev
# 浏览器打开 http://localhost:3000
```

### 阶段三：下达自然语言指令 (NL Controller)
授权完成后，即可进入“脱离浏览器”的自动化调度阶段。在终端启动对应的调度管家：

* **启动 BOSS 调度**：`python boss_scraper/boss_nl_controller.py`
* **启动猎聘调度**：`python liepin_scraper/liepin_nl_controller.py`
* **启动 51job 调度**：`python 51job_scraper/51job_nl_controller.py`

**🎉 引擎点火：**
在终端直接输入自然语言需求，系统会自动处理薪资映射、城市转换及翻页逻辑。
> **指令示例**：*"帮我抓取广州和深圳的 AI 产品经理，薪资 20-30k，抓取前 3 页数据。"*

*(⚠️ 提示：为确保成功越过风控，Boss 采集时系统会在需要时自动弹出浏览器新标签页，请勿关闭，抓取结束后可手动清理。)*

---

## 📂 核心目录解析

* `common/`：全局配置与飞书底层 API。
* `data/`：SQLite WAL 数据库。
* `boss_scraper/` & `51job_scraper/` & `liepin_scraper/`：三大平台物理隔离的自动化抓取引擎。
* `job_processor/`：数据处理大脑，包含 `rule_config.json` (一票否决黑名单)。
* `ai_agents/` & `multi_agent_workflow/`：基于 LangGraph 的简历/话术重写工厂。
* `backend/`：FastAPI 调度器。
* `frontend/`：Zustand + SSE 驱动的现代化 React 前端。

---

## ⚠️ 免责声明 (Disclaimer)

1. 本项目开源仅供**编程学习与 AI 自动化工作流交流**使用。
2. 请合理控制抓取频率，尊重各大招聘平台的服务器资源。**滥用极高频率并发抓取导致封号，作者概不负责。**
3. 代码中已包含适当的随机休眠与防风控机制，但在使用全自动投递功能时，请务必检查大模型生成的话术，避免社死。

## 🤝 参与贡献 (Contributing)
如果你觉得这个项目很酷，欢迎提交 PR 优化底层逻辑，或者添加更多的招聘平台支持！也欢迎在 Issue 区讨论 AI 求职的更多可能性。

## 🙏 致谢 (Acknowledgments)
本项目的诞生离不开开源社区的灵感与前人的探索，特此致谢以下优秀的开源项目：
* **终端 CLI 交互与登录授权逻辑**：部分参考自 [jackwener/boss-cli](https://github.com/jackwener/boss-cli)。
* **10 维度 AI 简历深度评估模型**：部分灵感与评估维度参考自 [santifer/career-ops](https://github.com/santifer/career-ops)。

---
**⭐️ 如果这个工具帮你拿到了心仪的 Offer，请给它点个 Star！**
```

## ⚖️ 版权声明 (License)

Copyright (c) 2026 Jolie Zeng (jolie-z). All rights reserved.

本项目源代码及相关文档仅供**个人学习、技术研究及非商业性质的交流使用**。
未经作者（Jolie Zeng）明确书面许可，严禁将本项目用于任何形式的商业用途（包括但不限于：作为 SaaS 服务提供、二次打包售卖、嵌入商业产品中牟利等）。商用授权请联系作者沟通。
