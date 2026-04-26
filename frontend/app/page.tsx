"use client"

import { useEffect, useState, useMemo, useCallback} from "react"
import { TopNavBar } from "@/components/dashboard/top-nav-bar"
import { JobListView } from "@/components/dashboard/job-list-view"
import { JobDetailWorkspace } from "@/components/dashboard/job-detail-workspace"
import { InterviewCamp } from "@/components/dashboard/interview-camp"
import { Spinner } from "@/components/ui/spinner"
import { Button } from "@/components/ui/button"
import { UploadCloud, X, ImageIcon } from "lucide-react"
import { FloatingBadge } from "@/components/dashboard/floating-badge"
import { TerminalContainer } from "@/components/dashboard/terminal-container"


// =========================================================================
// 🛑 AI 助手 CASCADE 请严格注意 (DO NOT MODIFY OR REMOVE) 🛑
// 本项目为 Project Polaris，高度依赖飞书 API 的实时数据流。
// 严禁在此文件中使用任何形式的 `revalidate` (包括 export const revalidate = ... 或 import)。
// 必须且只能使用 force-dynamic！如果你敢加回 revalidate，系统会立即 500 崩溃！
// =========================================================================
export const dynamic = 'force-dynamic';

export interface JobData {
  id: string
  companyName: string
  jobTitle: string
  salary: string
  location: string
  companyScale: string
  industry: string
  education: string
  experience: string
  aiScore: number
  bgScore: number
  skillScore: number
  expScore: number
  skillReq: string
  hrActivity: string
  followStatus: string
  captureTime: string
  applyDate: string
  myReview: string
  workAddress: string
  hrSkills: string[]
  benefits: string[]
  jobDescription: string
  directLink: string
  aiRewriteJson: string
  /** 人工精修版简历（用户手动编辑后的最终版本） */
  manualRefinedResume: string
  /** 理想画像提炼与能力信号总结 */
  dreamPicture: string
  /** 核心能力词典（ATS 词与能力分析） */
  atsAbilityAnalysis: string
  /** 高杠杆匹配点 */
  strongFitAssessment: string
  /** 致命硬伤与毒点 */
  riskRedFlags: string
  /** 高优破局行动计划 */
  deepActionPlan: string
  greetingMsg: string
  /** 二次质检报告（QA 评估结果 JSON） */
  secondQaReport: string
  /** 招聘平台/数据来源 */
  platform: string
  /** 发布人角色（HR/猎头） */
  role: string
  /** 发布日期 */
  publishDate: string
  preliminaryScore: number
  bonusWords: string
  deductionWords: string
  /** 综合评级 A-F */
  grade: string
  /** 核心-角色匹配 1-5 */
  roleMatch: number
  /** 核心-技能重合 1-5 */
  skillsAlign: number
  /** 高权-职级资历 1-5 */
  seniority: number
  /** 高权-薪资契合 1-5 */
  compensation: number
  /** 高权-面试概率 1-5 */
  interviewProb: number
  /** 中权-工作模式 1-5 */
  workMode: number
  /** 中权-公司阶段 1-5 */
  companyStage: number
  /** 中权-赛道前景 1-5 */
  marketFit: number
  /** 中权-成长空间 1-5 */
  growth: number
  /** 低权-招聘周期 1-5 */
  timeline: number
  /** AI 评估详情（10维度打分依据） */
  aiEvaluationDetail: string
}

export type GlobalView = "immersive-list" | "immersive-detail" | "interview-camp"

export default function Dashboard() {
  const [currentView, setCurrentView] = useState<GlobalView>("immersive-list")
  const [jobs, setJobs] = useState<JobData[]>([])
  const [currentNavJobs, setCurrentNavJobs] = useState<JobData[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedJob, setSelectedJob] = useState<JobData | null>(null)
  const [processingJobs, setProcessingJobs] = useState<Record<string, string>>({})
  const [jobLiveLogs, setJobLiveLogs] = useState<Record<string, string[]>>({})
  const [globalTaskStatus, setGlobalTaskStatus] = useState<"idle" | "running" | "completed">("idle")
  // 🌟 极速录入状态
  const [isImportModalOpen, setIsImportModalOpen] = useState(false)
  const [importText, setImportText] = useState("")
  const [isImporting, setIsImporting] = useState(false)
  // 🌟 多图上传状态
  const [importImages, setImportImages] = useState<string[]>([])

  // 将文件转为 Base64
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return

    files.forEach(file => {
      const reader = new FileReader()
      reader.readAsDataURL(file)
      reader.onload = () => {
        setImportImages(prev => [...prev, reader.result as string])
      }
    })
    e.target.value = '' // 允许重复上传相同图片
  }

  // 移除单张图片
  const handleRemoveImage = (indexToRemove: number) => {
    setImportImages(prev => prev.filter((_, index) => index !== indexToRemove))
  }
  // 🌟 新增：监听剪贴板的粘贴事件（支持直接 Cmd+V / Ctrl+V 粘贴图片）
  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return

    let hasImage = false
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf("image") !== -1) {
        hasImage = true
        const file = items[i].getAsFile()
        if (!file) continue
        
        const reader = new FileReader()
        reader.readAsDataURL(file)
        reader.onload = () => {
          setImportImages(prev => [...prev, reader.result as string])
        }
      }
    }
    
    // 如果剪贴板里有图片，就阻止默认的粘贴行为（防止把图片当成乱码文字粘进文本框里）
    if (hasImage) {
      e.preventDefault()
    }
  }

  // 🌟 增加 silent 参数，默认为 false（即默认显示加载中）
  const fetchJobs = async (silent = false) => {
    try {
      if (!silent) setIsLoading(true)
      const response = await fetch("http://127.0.0.1:8000/jobs", {
        cache: 'no-store',
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache'
        }
      })
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`)
      }
      const data = await response.json()
      console.log("Fetched jobs:", data)
      type JobsApiItem = {
        record_id?: string | number
        job_name?: string
        company_name?: string
        city?: string
        salary?: string
        follow_status?: string
        scale?: string
        industry?: string
        education?: string
        experience?: string
        ai_score?: number
        bg_score?: number
        skill_score?: number
        exp_score?: number
        skill_req?: string
        job_detail?: string
        hr_skills?: string[]
        benefits?: string[]
        hr_active?: string
        delivery_date?: string
        fetch_time?: string
        work_address?: string
        manual_refined_resume?: string
        my_review?: string
        ai_rewrite_json?: string
        dream_picture?: string
        ats_ability_analysis?: string
        strong_fit_assessment?: string
        risk_red_flags?: string
        deep_action_plan?: string
        greeting_msg?: string
        platform?: string
        role?: string
        publish_date?: string
        second_qa_report?: string
        preliminary_score?: number
        bonus_words?: string
        deduction_words?: string
        grade?: string
        role_match?: number
        skills_align?: number
        seniority?: number
        compensation?: number
        interview_prob?: number
        work_mode?: number
        company_stage?: number
        market_fit?: number
        growth?: number
        timeline?: number
        ai_evaluation_detail?: string
        job_link?: string
      }

      const items: JobsApiItem[] = Array.isArray(data) ? data : (Array.isArray(data?.items) ? data.items : [])
      const normalizedJobs: JobData[] = items.map((item: JobsApiItem, index: number): JobData => {
        // 🌟 使用 platform + record_id 组合确保全局唯一 ID
        const platform = item.platform ?? "未知"
        const recordId = String(item.record_id ?? `temp-${index}`)
        const uniqueId = `${platform}-${recordId}`
        
        return {
            id: uniqueId,
            companyName: item.company_name ?? "未知公司",
            jobTitle: item.job_name ?? "未知职位",
            salary: item.salary ?? "-",
            location: item.city ?? "-",
            companyScale: item.scale ?? "-",
            industry: item.industry ?? "-",
            education: item.education ?? "-",
            experience: item.experience ?? "-",
            aiScore: Number(item.ai_score ?? 0),
            bgScore: Number(item.bg_score ?? 0),
            skillScore: Number(item.skill_score ?? 0),
            expScore: Number(item.exp_score ?? 0),
            skillReq: item.skill_req ?? "",
            hrActivity: item.hr_active ?? "-",
            followStatus: item.follow_status ?? "待投递",
            captureTime: item.fetch_time ?? "-",
            applyDate: item.delivery_date ?? "-",
            myReview: item.my_review ?? "-",
            workAddress: item.work_address ?? "-",
            hrSkills: Array.isArray(item.hr_skills) ? item.hr_skills : [],
            benefits: Array.isArray(item.benefits) ? item.benefits : [],
            jobDescription: item.job_detail ?? "",
            directLink: item.job_link && item.job_link !== "-" ? item.job_link : "#",
            aiRewriteJson: item.ai_rewrite_json ?? "",
            manualRefinedResume: item.manual_refined_resume ?? "",
            dreamPicture: item.dream_picture ?? "",
            atsAbilityAnalysis: item.ats_ability_analysis ?? "",
            strongFitAssessment: item.strong_fit_assessment ?? "",
            riskRedFlags: item.risk_red_flags ?? "",
            deepActionPlan: item.deep_action_plan ?? "",
            greetingMsg: item.greeting_msg ?? "",
            secondQaReport: item.second_qa_report ?? "",
            platform: platform,
            role: item.role ?? "未知",
            publishDate: item.publish_date ?? "-",
            preliminaryScore: Number(item.preliminary_score ?? 0),
            bonusWords: item.bonus_words ?? "-",
            deductionWords: item.deduction_words ?? "-",
            grade: item.grade ?? "",
            roleMatch: Number(item.role_match ?? 0),
            skillsAlign: Number(item.skills_align ?? 0),
            seniority: Number(item.seniority ?? 0),
            compensation: Number(item.compensation ?? 0),
            interviewProb: Number(item.interview_prob ?? 0),
            workMode: Number(item.work_mode ?? 0),
            companyStage: Number(item.company_stage ?? 0),
            marketFit: Number(item.market_fit ?? 0),
            growth: Number(item.growth ?? 0),
            timeline: Number(item.timeline ?? 0),
            aiEvaluationDetail: item.ai_evaluation_detail ?? "",
          }
      })

      setJobs(normalizedJobs)
      setSelectedJob((prev) =>
        prev ? normalizedJobs.find((job: JobData) => job.id === prev.id) ?? normalizedJobs[0] ?? null : null,
      )
    } catch (error) {
      console.error("Failed to fetch jobs:", error)
      setJobs([])
      setSelectedJob(null)
    } finally {
      setIsLoading(false)
    }
  }

  const handleBatchDelete = async (jobIds: string[]) => {
    try {
      const response = await fetch("http://127.0.0.1:8000/api/jobs/batch-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_ids: jobIds }),
      })

      const data = await response.json()
      if (response.ok && data.status === "success") {
        setJobs(prevJobs => prevJobs.filter(job => !jobIds.includes(job.id)))
        alert(`✅ ${data.message}`)
      } else {
        alert("❌ 删除失败：" + (data.detail || data.message || "未知错误"))
      }
    } catch (error) {
      console.error("批量删除请求失败:", error)
      alert("❌ 网络错误，批量删除失败")
    }
  }

  useEffect(() => {
    fetchJobs()
  }, [])

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail
      if (Array.isArray(detail?.jobIds) && detail?.taskType) {
        setProcessingJobs(Object.fromEntries(detail.jobIds.map((id: string) => [id, detail.taskType as string])))
        setJobLiveLogs({})
        setGlobalTaskStatus("running")
      }
    }
    window.addEventListener('START_GLOBAL_TASK', handler)
    return () => window.removeEventListener('START_GLOBAL_TASK', handler)
  }, [])

  const handleSseMessage = useCallback((data: any) => {
    if (!data) return;

    // 🚀 核心 1：智能 ID 寻找逻辑
    // 后端可能只传 record_id，但前端 key 是 "platform-record_id"
    // 我们在 processingJobs 中寻找真正匹配的那个 key
    const rawId = data.job_id || data.record_id;
    let targetKey = rawId;
    
    if (rawId) {
      const activeKeys = Object.keys(processingJobs);
      const matchedKey = activeKeys.find(key => key === rawId || key.endsWith(`-${rawId}`));
      if (matchedKey) targetKey = matchedKey;
    }

    if (targetKey && data.message) {
      setJobLiveLogs(prev => ({
        ...prev,
        [targetKey]: [...(prev[targetKey] ?? []), data.message].slice(-3)
      }))
    }

    // 核心 2：捕捉结束信号，立即解除转圈并更新
    const isFinished = 
      (data.message && (data.message.includes('Token 消耗') || data.message.includes('成功加载'))) ||
      data.type === 'success' || 
      data.type === 'error';

    if (isFinished && targetKey) {
      // 1. 立即解除该岗位的转圈状态（Evaluate 信号消失）
      setProcessingJobs(prev => {
        const next = { ...prev };
        delete next[targetKey];
        return next;
      });
      
      // 2. 如果后端传了具体的更新数据，执行局部热更新
      if (data.job_updates) {
        setJobs(prev => prev.map(job => job.id === targetKey ? { ...job, ...data.job_updates } : job));
      } else {
        // 3. 兜底：如果后端没传局部更新包，执行静默刷新拉取全量最新数据
        // 使用 silent=true 确保用户界面不抖动、不锁死
        fetchJobs(true);
      }
    }

    if (data.type === 'end' || data.type === 'complete') {
      // SSE 收到 end 时，如果还没被轮询捕捉到，也执行完结动作
      if (globalTaskStatus === "running") {
        setGlobalTaskStatus("completed");
        setProcessingJobs({});
        fetchJobs(true);
        setTimeout(() => {
          setGlobalTaskStatus("idle");
          setJobLiveLogs({});
        }, 3000);
      }
    }
  }, [processingJobs, fetchJobs, globalTaskStatus]);

  // 🌟 核心修复：短轮询护航机制
  // 当 globalTaskStatus 为 running 时，每隔 3 秒向后端确认一次真实状态
  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    if (globalTaskStatus === "running") {
      intervalId = setInterval(async () => {
        try {
          const res = await fetch("http://127.0.0.1:8000/api/tasks/status");
          const data = await res.json();

          // 如果后端明确返回 false，说明后台确实没任务了，但前端还没解除锁定
          if (data.is_processing === false) {
            console.log("🔄 轮询检测到后台任务已结束，强制解除前端锁定");

            setGlobalTaskStatus("completed");
            setProcessingJobs({});
            fetchJobs(true); // 静默刷新列表

            // 3秒后恢复 idle
            setTimeout(() => {
              setGlobalTaskStatus("idle");
              setJobLiveLogs({});
            }, 3000);
          }
        } catch (error) {
          console.error("轮询任务状态失败:", error);
        }
      }, 3000); // 每 3 秒问一次
    }

    // 当组件卸载或状态不再是 running 时，清理定时器
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [globalTaskStatus, fetchJobs]);

  // 🌟 处理极速录入（智能图文分流）
  const handleQuickImport = async () => {
    if (!importText.trim() && importImages.length === 0) {
      return alert("请粘贴文本或上传至少一张截图！")
    }
    
    setIsImporting(true)
    try {
      let response;
      
      // 智能分流：有图走视觉接口，纯文本走文本接口
      if (importImages.length > 0) {
        response = await fetch("http://127.0.0.1:8000/api/jobs/import/image", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ images_base64: importImages })
        })
      } else {
        response = await fetch("http://127.0.0.1:8000/api/jobs/import/text", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ raw_text: importText })
        })
      }
      
      const result = await response.json()
      if (response.ok) {
        alert("✅ 解析成功并已同步到飞书！")
        setImportText("")
        setImportImages([]) // 清空图片
        setIsImportModalOpen(false)
        fetchJobs() // 刷新列表
      } else {
        alert(`❌ 录入失败: ${result.detail || "未知错误"}`)
      }
    } catch (error) {
      alert("❌ 网络请求失败，请检查后端服务")
    } finally {
      setIsImporting(false)
    }
  }
  // 使用 useMemo 动态计算状态统计和可用状态列表
  const statusCounts = useMemo(() => {
    return jobs.reduce<Record<string, number>>((acc, job) => {
      const status = job.followStatus?.trim()
      // 过滤掉空值、未定义、"-" 等异常状态
      if (status && status !== "-" && status !== "未标注") {
        acc[status] = (acc[status] ?? 0) + 1
      }
      return acc
    }, {})
  }, [jobs])

  // 🌟 预设飞书的标准跟进状态字典，确保下拉菜单始终有全量选项可供切换
  const PRESET_STATUSES = [
    "新线索",
    "不合适",
    "已完成初步评估",
    "已完成深度评估",
    "简历人工复核",
    "待投递",
    "已投递",
    "面试中",
    "Offer",
    "已下架",
  ]

  // 提取所有不重复的跟进状态，并与预设状态合并去重
  const dynamicStatuses = useMemo(() => {
    const fetchedStatuses = Object.keys(statusCounts)
    return Array.from(new Set([...PRESET_STATUSES, ...fetchedStatuses]))
  }, [statusCounts])

  const handleEnterDetail = (job: JobData, filteredList?: JobData[]) => {
    setSelectedJob(job)
    setCurrentView("immersive-detail")
    if (filteredList) {
      setCurrentNavJobs(filteredList)
    }
  }

  // 🌟 【修改这里】增强更新逻辑，支持“删除并跳到下一个”
  const handleUpdateSelectedJob = (nextJob: JobData | null, action?: 'remove') => {
    if (action === 'remove' && selectedJob) {
      // 1. 如果是删除操作（如标记为不合适），瞬间把它从列表中过滤掉
      const filteredJobs = jobs.filter(j => j.id !== selectedJob.id)
      setJobs(filteredJobs)
      
      // 🌟 同步过滤 currentNavJobs
      const filteredNavJobs = currentNavJobs.filter(j => j.id !== selectedJob.id)
      setCurrentNavJobs(filteredNavJobs)
      
      // 2. 自动跳转到下一个（如果有的话），或者返回列表（基于 currentNavJobs）
      const currentIndex = currentNavJobs.findIndex((job) => job.id === selectedJob.id)
      if (currentIndex < filteredNavJobs.length) {
        setSelectedJob(filteredNavJobs[currentIndex]) // 显示原来的下一个
      } else if (filteredNavJobs.length > 0) {
        setSelectedJob(filteredNavJobs[filteredNavJobs.length - 1]) // 没下一个了就显示上一个
      } else {
        handleBackToList() // 列表空了就退回主界面
      }
    } else if (nextJob) {
      // 普通的状态更新（非删除），直接改本地数据，不刷新页面
      setSelectedJob(nextJob)
      setJobs((prev) => prev.map((job) => (job.id === nextJob.id ? nextJob : job)))
      // 🌟 同步更新 currentNavJobs
      setCurrentNavJobs((prev) => prev.map((job) => (job.id === nextJob.id ? nextJob : job)))
    }
  }

  const handleBackToList = () => {
    setCurrentView("immersive-list")
    setSelectedJob(null)
  }

  const handleMainTabChange = (tab: "immersive" | "interview") => {
    if (tab === "interview") {
      setCurrentView("interview-camp")
    } else {
      setCurrentView("immersive-list")
    }
    setSelectedJob(null)
  }

  // 🌟 智能导航列表：优先使用 L1 传来的过滤列表，否则回退到全局 jobs
  const navigationList = currentNavJobs.length > 0 ? currentNavJobs : jobs

  // 计算当前选中岗位的索引（基于 navigationList）
  const currentJobIndex = selectedJob ? navigationList.findIndex((job) => job.id === selectedJob.id) : -1
  const hasPrevious = currentJobIndex > 0
  const hasNext = currentJobIndex >= 0 && currentJobIndex < navigationList.length - 1

  // 切换到上一个岗位
  const handlePrevious = () => {
    if (hasPrevious && currentJobIndex > 0) {
      setSelectedJob(navigationList[currentJobIndex - 1])
    }
  }

  // 切换到下一个岗位
  const handleNext = () => {
    if (hasNext && currentJobIndex < navigationList.length - 1) {
      setSelectedJob(navigationList[currentJobIndex + 1])
    }
  }

  return (
    <div className="flex flex-col h-screen bg-muted/30">
      <TopNavBar
        currentView={currentView}
        onMainTabChange={handleMainTabChange}
        statusCounts={statusCounts}
      />
      <main className="flex-1 overflow-hidden">
        {isLoading && (
          <div className="h-full flex items-center justify-center">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner className="size-5" />
              正在加载岗位数据...
            </div>
          </div>
        )}
        {!isLoading && currentView === "immersive-list" && (
          <JobListView
            jobs={jobs}
            onEnterDetail={handleEnterDetail}
            dynamicStatuses={dynamicStatuses}
            onRefreshJobs={fetchJobs}
            onOpenImport={() => setIsImportModalOpen(true)}
            processingJobs={processingJobs}
            jobLiveLogs={jobLiveLogs}
            onBatchDelete={handleBatchDelete}
            globalTaskStatus={globalTaskStatus}
          />
        )}
        {!isLoading && currentView === "immersive-detail" && selectedJob && (
          <JobDetailWorkspace
            job={selectedJob}
            onUpdateJob={handleUpdateSelectedJob}
            onBack={handleBackToList}
            hasPrevious={hasPrevious}
            hasNext={hasNext}
            onPrevious={handlePrevious}
            onNext={handleNext}
            dynamicStatuses={dynamicStatuses}
            onRefreshJobs={fetchJobs}
          />
        )}
        {!isLoading && currentView === "interview-camp" && <InterviewCamp />}
        {/* 🌟 极速录入弹窗 (多图智能版) */}
        {isImportModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="w-[550px] bg-white rounded-2xl shadow-2xl p-6 flex flex-col gap-4 max-h-[90vh] overflow-hidden">
              <div className="flex justify-between items-center shrink-0">
                <h3 className="text-lg font-bold text-gray-800">➕ 全渠道极速录入</h3>
                <button 
                  onClick={() => { setIsImportModalOpen(false); setImportImages([]); setImportText(""); }} 
                  className="text-gray-400 hover:text-gray-600 p-1"
                >
                  <X size={20} />
                </button>
              </div>
              
              <div className="flex-1 overflow-y-auto pr-2 space-y-4">
                <p className="text-xs text-muted-foreground bg-blue-50/50 p-2.5 rounded border border-blue-100/50">
                  💡 提示：你可以粘贴文字，或上传多张招聘截图。AI 将自动提取结构化数据并同步飞书。若同时上传图文，将优先解析图片。
                </p>

                {/* 文本输入区 */}
                <textarea
                  value={importText}
                  onChange={(e) => setImportText(e.target.value)}
                  onPaste={handlePaste}  // 🌟 只需要加这一行！
                  placeholder="在此粘贴文本，或直接 Cmd+V / Ctrl+V 粘贴截图..."
                  className="h-32 w-full p-4 border border-border rounded-xl focus:ring-2 focus:ring-primary outline-none resize-none text-sm bg-gray-50/50"
                />

                {/* 图片上传与预览区 */}
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-gray-700 flex items-center gap-1.5">
                      <ImageIcon size={16} /> 招聘截图 ({importImages.length})
                    </span>
                    
                    {/* 隐藏的文件输入框，通过 label 触发 */}
                    <label className="cursor-pointer text-xs flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md transition-colors">
                      <UploadCloud size={14} /> 上传图片
                      <input 
                        type="file" 
                        multiple 
                        accept="image/*" 
                        className="hidden" 
                        onChange={handleImageUpload}
                      />
                    </label>
                  </div>

                  {/* 缩略图横向展示区 */}
                  {importImages.length > 0 && (
                    <div className="flex gap-3 overflow-x-auto pb-2 custom-scrollbar">
                      {importImages.map((imgBase64, idx) => (
                        <div key={idx} className="relative group shrink-0 w-24 h-32 rounded-lg border border-gray-200 overflow-hidden bg-gray-50">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={imgBase64} alt={`upload-${idx}`} className="w-full h-full object-cover" />
                          <button 
                            onClick={() => handleRemoveImage(idx)}
                            className="absolute top-1 right-1 bg-red-500/80 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600"
                          >
                            <X size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="flex justify-end gap-3 shrink-0 pt-2 border-t border-gray-100 mt-2">
                <Button variant="ghost" onClick={() => setIsImportModalOpen(false)}>取消</Button>
                <Button onClick={handleQuickImport} disabled={isImporting} className="gap-2">
                  {isImporting ? <Spinner className="size-4" /> : null}
                  {isImporting ? "解析中..." : "开始解析并录入"}
                </Button>
              </div>
            </div>
          </div>
        )}
        {/* 🌟 全局悬浮多开控制台系统 */}
        {currentView === "immersive-list" && (
          <>
            <FloatingBadge />
            <TerminalContainer onComplete={fetchJobs} onSseMessage={handleSseMessage} />
          </>
        )}
      </main>
    </div>
  )
}
