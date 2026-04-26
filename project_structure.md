51job_scraper/
├── 51job_collector.py        # [核心] 数据采集器：负责 Playwright 页面抓取与解析入库
├── 51job_nl_controller.py     # [调度] 自然语言管家：将口语指令转换为采集任务流
├── 51job_cookie_harvester.py  # [工具] Cookie 采集器：手动扫码获取登录凭证
├── 51job_auto_delivery.py     # [扩展] 自动投递脚本：结合浏览器自动化与附件简历上传
├── auto_send_messgae.py       # [测试] GUI 发信逻辑：基于 pyautogui 的物理模拟发信（实验性）
└── 51job_cookies.json         # [私有] 登录凭证：存储账号 Session（⚠️ 严禁上传至 GitHub）
liepin_scraper/            # 🟠 猎聘专区 
├── liepin_crawler.py              # [核心] 数据采集器
├── liepin_nl_controller.py        # [调度] 猎聘自然语言管家
├── liepin_cookie_harvester.py     # [工具] Cookie 获取器
├── liepin_auto_delivery.py        # [扩展] 猎聘自动投递执行器
└── liepin_delivery_scheduler.py   # [扩展] 猎聘投递任务调度器
boss_scraper/              # 🔵 Boss 直聘专区 
├── boss_collector.py          # [核心/原data_collector] 列表页抓取与前置去重
├── boss_detail_fetcher.py     # [核心/原job_detail_fetcher] 详情页深度解析
├── boss_nl_controller.py      # [调度] 动态目标与分页管家
└── boss_auto_delivery.py      # [扩展] 自动投递执行引擎
├── boss_cookie_harvester.py   # [工具] 手动扫码获取 Cookie
├── auth.py                    # 授权与 Cookie 校验逻辑
├── client.py                  # API 请求底层封装
├── exceptions.py              # 异常类统一定义
├── index_cache.py             # 索引与去重缓存管理
├── constants.py               # 全局常量配置
├── cli.py                     # 兼容命令行的基础支持
└── __init__.py                # 包初始化声明
data/
├── .gitkeep               # [新增] 一个隐藏文件，用来保证 Git 会追踪这个空文件夹
└── db_manager.py          # [保留] 数据库初始化与表结构管理工具
job_processor/
├── rule_config.json        # [配置] 关键词分值与一票否决(Veto)黑名单
├── structural_filter.py    # [工具] 基础过滤规则引擎类
├── step1_rule_filter.py    # [执行] 第1步：硬规则清洗与初步打分 
├── step2_sync_feishu.py    # [执行] 第2步：推送至飞书多维表格 
└── step3_ai_evaluator.py   # [执行] 第3步：大模型深度打分与评价 
ai_agents/                 # 🤖 大模型智能体专区 (本轮整理)
├── ai_scorer.py           # [底层] 大模型交互引擎 (LLM/Serper/Prompt管理)
├── ai_evaluator.py        # [执行] 岗位深度诊断评估器
├── apply_assistant.py     # [执行] 定制化简历与话术生成器
├── greeting_ab_tester.py  # [测试] 话术批量生成的 A/B 测试工具
└── auto_patrol.py         # [守护] 影帝级全自动巡逻挂机脚本
multi_agent/      # 🕸️ [新增] 基于 LangGraph 的多 Agent 简历重写流水线
    └── agent_workflow.py      # Splitter -> Architect -> Critic -> Formatter 核心逻辑
frontend/
├── app/                       # [核心] Next.js App Router 目录
│   ├── globals.css            # 🎨 全局样式与主题定义
│   ├── layout.tsx             # 🏗️ 根布局 (已移除个人统计脚本)
│   └── page.tsx               # 🚀 主看板：集成 Job 列表、AI 诊断与悬浮终端
│   └── strategy/
│       └── page.tsx           # 策略实验室页面入口
├── public/                    # [静态] 存放图标 (icon.svg 等)
├── components/                # [组件] 存放 shadcn/ui 及自定义业务组件
│   └── dashboard/             # 🛠️ 业务逻辑组件专区 (本轮整理)
│       ├── top-nav-bar.tsx    # 顶部导航
│       ├── job-list-view.tsx  # 岗位列表
│       ├── job-detail-workspace.tsx # 深度详情工作台
│       ├── strategy-lab.tsx   # [待修复] 简历模板管理与测试
│       ├── live-task-terminal.tsx # 终端实时渲染引擎
│       ├── terminal-container.tsx # 终端布局容器
│       ├── floating-badge.tsx # 最小化浮标
│       ├── floating-copilot-widget.tsx # 选中追问浮窗
│       └── interview-camp.tsx # 面试训练营 (Placeholder)
├── lib/                       # [工具] 存放 utils.ts 等
├── .gitignore                 # [核心] 已配置忽略 .next/ 和 node_modules/
├── next.config.mjs            # [配置] Next.js 运行配置
├── package.json               # [清单] 项目依赖与脚本 (已改为 pnpm 规范)
└── pnpm-lock.yaml             # [锁定] 唯一保留的包管理锁定文件 (已删除 package-lock.json)