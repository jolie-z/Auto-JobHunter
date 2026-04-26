"use client"

import { useState } from "react"
import {
  Search,
  Building2,
  MapPin,
  ChevronRight,
  Sparkles,
  FileEdit,
  Plus,
  RefreshCw,
  Brain,
  Loader2,
  Send,
  Trash2,
  Bot,
} from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { JobData } from "@/app/page"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface JobListViewProps {
  jobs: JobData[]
  onEnterDetail: (job: JobData, currentFilteredJobs: JobData[]) => void
  dynamicStatuses: string[]
  onRefreshJobs?: () => Promise<void> | void
  onOpenImport: () => void
  processingJobs?: Record<string, string>
  jobLiveLogs?: Record<string, string[]>
  onBatchDelete?: (jobIds: string[]) => Promise<void>
  globalTaskStatus?: "idle" | "running" | "completed"
}

export function JobListView({ jobs, onEnterDetail, dynamicStatuses, onRefreshJobs, onOpenImport, processingJobs = {}, jobLiveLogs = {}, onBatchDelete, globalTaskStatus = "idle" }: JobListViewProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState("全部")
  const [scoreFilter, setScoreFilter] = useState("全部")
  const [eduFilter, setEduFilter] = useState("全部")
  const [expFilter, setExpFilter] = useState("全部")
  const [scaleFilter, setScaleFilter] = useState("全部")
  const [platformFilter, setPlatformFilter] = useState("全部")
  
  // 🌟 批量操作状态
  const [selectedJobIds, setSelectedJobIds] = useState<string[]>([])
  const [isProcessing, setIsProcessing] = useState(false)
  const isBatchRunning = Object.keys(processingJobs).length > 0
  // 🌟 刷新列表状态
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [refreshed, setRefreshed] = useState(false)

  const filteredJobs = jobs.filter((job) => {
    const matchesSearch =
      (job.companyName || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (job.jobTitle || "").toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus = statusFilter === "全部" || job.followStatus === statusFilter
    const matchesEdu = eduFilter === "全部" || job.education === eduFilter
    const matchesExp = expFilter === "全部" || job.experience === expFilter
    const matchesScale = scaleFilter === "全部" || job.companyScale === scaleFilter
    const matchesPlatform = platformFilter === "全部" || job.platform === platformFilter

    let matchesScore = true
    const grade = job.grade ?? ""
    if (scoreFilter === "A") matchesScore = grade === "A"
    else if (scoreFilter === "B") matchesScore = grade === "B"
    else if (scoreFilter === "C") matchesScore = grade === "C"
    else if (scoreFilter === "D-F") matchesScore = grade === "D" || grade === "F"
    else if (scoreFilter === "未评估") matchesScore = !grade

    return matchesSearch && matchesStatus && matchesScore && matchesEdu && matchesExp && matchesScale && matchesPlatform
  })

  // 🌟 将已经处理过（存在评级 grade）的岗位置顶显示
  const sortedJobs = [...filteredJobs].sort((a, b) => {
    const aProcessed = a.grade ? 1 : 0;
    const bProcessed = b.grade ? 1 : 0;
    return bProcessed - aProcessed;
  });

  // 🌟 批量选择逻辑
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedJobIds(filteredJobs.map(job => job.id))
    } else {
      setSelectedJobIds([])
    }
  }

  const handleSelectJob = (jobId: string, checked: boolean) => {
    if (checked) {
      setSelectedJobIds(prev => [...prev, jobId])
    } else {
      setSelectedJobIds(prev => prev.filter(id => id !== jobId))
    }
  }

  // 🌟 刷新列表
  const handleRefresh = async () => {
    if (isRefreshing) return
    setIsRefreshing(true)
    setRefreshed(false)
    try {
      await onRefreshJobs?.()
    } finally {
      setIsRefreshing(false)
      setRefreshed(true)
      setTimeout(() => setRefreshed(false), 2000)
    }
  }

  // 🌟 批量 AI 评估
  const handleBatchEvaluate = async () => {
    if (selectedJobIds.length === 0) return
    
    setIsProcessing(true)
    try {
      const response = await fetch('http://127.0.0.1:8000/api/tasks/batch-process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_type: 'evaluate',
          job_ids: selectedJobIds
        })
      })
      
      const data = await response.json()
      
      if (response.ok) {
        console.log('🚀 批量评估任务已启动:', data.task_id)
        
        // 🌟 抛出全局事件，通知悬浮终端自动展开并连接 SSE
        window.dispatchEvent(new CustomEvent('START_GLOBAL_TASK', {
          detail: {
            taskId: data.task_id,
            title: `批量 AI 评估任务 (${selectedJobIds.length}个岗位)`,
            jobIds: selectedJobIds,
            taskType: 'evaluate'
          }
        }))

        setIsProcessing(false)
        setSelectedJobIds([])
      } else {
        alert('❌ 启动任务失败: ' + (data.detail || '未知错误'))
        setIsProcessing(false)
      }
    } catch (error) {
      console.error('❌ 批量评估错误:', error)
      alert('❌ 网络错误，请检查后端是否运行')
      setIsProcessing(false)
    }
  }

  // 🌟 批量简历改写
  const handleBatchRewrite = async () => {
    if (selectedJobIds.length === 0) return
    
    setIsProcessing(true)
    try {
      const response = await fetch('http://127.0.0.1:8000/api/tasks/batch-process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_type: 'rewrite',
          job_ids: selectedJobIds
        })
      })
      
      const data = await response.json()
      
      if (response.ok) {
        console.log('🚀 批量改写任务已启动:', data.task_id)
        
        // 🌟 抛出全局事件，通知悬浮终端自动展开并连接 SSE
        window.dispatchEvent(new CustomEvent('START_GLOBAL_TASK', {
          detail: {
            taskId: data.task_id,
            title: `批量简历改写任务 (${selectedJobIds.length}个岗位)`,
            jobIds: selectedJobIds,
            taskType: 'rewrite'
          }
        }))

        setIsProcessing(false)
        setSelectedJobIds([])
      } else {
        alert('❌ 启动任务失败: ' + (data.detail || '未知错误'))
        setIsProcessing(false)
      }
    } catch (error) {
      console.error('❌ 批量改写错误:', error)
      alert('❌ 网络错误，请检查后端是否运行')
      setIsProcessing(false)
    }
  }


  // 🌟 批量多Agent深度改写
  const handleBatchDeepRewrite = async () => {
    console.log("👉 [前端] 多Agent按钮被点击，当前选中岗位:", selectedJobIds);
    if (selectedJobIds.length === 0) return
    
    setIsProcessing(true)
    try {
      const response = await fetch('http://127.0.0.1:8000/api/tasks/batch-process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_type: 'deep_rewrite',
          job_ids: selectedJobIds
        })
      })
      
      const data = await response.json()
      
      if (response.ok) {
        console.log('🚀 批量多Agent深度改写任务已启动:', data.task_id)
        
        // 🌟 抛出全局事件，通知悬浮终端自动展开并连接 SSE
        window.dispatchEvent(new CustomEvent('START_GLOBAL_TASK', {
          detail: {
            taskId: data.task_id,
            title: `批量多Agent深度改写任务 (${selectedJobIds.length}个岗位)`,
            jobIds: selectedJobIds,
            taskType: 'deep_rewrite'
          }
        }))

        setIsProcessing(false)
        setSelectedJobIds([])
      } else {
        alert('❌ 启动任务失败: ' + (data.detail || '未知错误'))
        setIsProcessing(false)
      }
    } catch (error) {
      console.error('❌ 批量多Agent深度改写错误:', error)
      alert('❌ 网络错误，请检查后端是否运行')
      setIsProcessing(false)
    }
  }


  // 🌟 批量自动投递
  const handleBatchDeliver = async () => {
    if (selectedJobIds.length === 0) return

    const scheduledInput = window.prompt(
      '请输入定时执行的时间（留空则立即执行，格式：YYYY-MM-DD HH:mm）\n例：2026-04-21 09:00'
    )
    // 用户点取消时 scheduledInput 为 null，视为放弃操作
    if (scheduledInput === null) return

    const scheduledAt = scheduledInput.trim() || null

    setIsProcessing(true)
    try {
      const response = await fetch('http://127.0.0.1:8000/api/tasks/batch-process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_type: 'deliver',
          job_ids: selectedJobIds,
          ...(scheduledAt ? { scheduled_at: scheduledAt } : {})
        })
      })

      const data = await response.json()

      if (response.ok) {
        console.log('🚀 批量自动投递任务已启动:', data.task_id)

        window.dispatchEvent(new CustomEvent('START_GLOBAL_TASK', {
          detail: {
            taskId: data.task_id,
            title: `批量自动投递任务 (${selectedJobIds.length}个岗位)`,
            jobIds: selectedJobIds,
            taskType: 'deliver'
          }
        }))

        setIsProcessing(false)
        setSelectedJobIds([])
      } else {
        alert('❌ 启动任务失败: ' + (data.detail || '未知错误'))
        setIsProcessing(false)
      }
    } catch (error) {
      console.error('❌ 批量自动投递错误:', error)
      alert('❌ 网络错误，请检查后端是否运行')
      setIsProcessing(false)
    }
  }

  // 🌟 批量 AI 深度评估
  const handleBatchDeepEvaluate = async () => {
    if (selectedJobIds.length === 0) return

    setIsProcessing(true)
    try {
      const response = await fetch('http://127.0.0.1:8000/api/tasks/batch-process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_type: 'deep_evaluate',
          job_ids: selectedJobIds
        })
      })

      const data = await response.json()

      if (response.ok) {
        console.log('🧠 批量深度评估任务已启动:', data.task_id)

        window.dispatchEvent(new CustomEvent('START_GLOBAL_TASK', {
          detail: {
            taskId: data.task_id,
            title: `批量 AI 深度评估任务 (${selectedJobIds.length}个岗位)`,
            jobIds: selectedJobIds,
            taskType: 'deep_evaluate'
          }
        }))

        setIsProcessing(false)
        setSelectedJobIds([])
      } else {
        alert('❌ 启动任务失败: ' + (data.detail || '未知错误'))
        setIsProcessing(false)
      }
    } catch (error) {
      console.error('❌ 批量深度评估错误:', error)
      alert('❌ 网络错误，请检查后端是否运行')
      setIsProcessing(false)
    }
  }


  return (
    <div className="h-full flex flex-col">
      {/* Filter Bar */}
      <div className="px-6 py-4 border-b border-border bg-card flex flex-col gap-4">
        {/* 第一行：搜索与多重筛选条件 */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 max-w-xs min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="搜索公司或职位..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 h-9 text-sm"
            />
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-32 h-9 text-xs"><SelectValue placeholder="跟进状态" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="全部">全部状态</SelectItem>
                {dynamicStatuses.map((status) => (
                  <SelectItem key={status} value={status}>{status}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={scoreFilter} onValueChange={setScoreFilter}>
              <SelectTrigger className="w-32 h-9 text-xs"><SelectValue placeholder="评级筛选" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="全部">全部评级</SelectItem>
                <SelectItem value="A">🏆 A级 - 顶级匹配</SelectItem>
                <SelectItem value="B">✅ B级 - 良好</SelectItem>
                <SelectItem value="C">🔵 C级 - 一般</SelectItem>
                <SelectItem value="D-F">⚠️ D/F级 - 较差</SelectItem>
                <SelectItem value="未评估">📋 未评估</SelectItem>
              </SelectContent>
            </Select>
            <Select value={eduFilter} onValueChange={setEduFilter}>
              <SelectTrigger className="w-24 h-9 text-xs"><SelectValue placeholder="学历" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="全部">全部学历</SelectItem>
                <SelectItem value="学历不限">学历不限</SelectItem>
                <SelectItem value="本科">本科</SelectItem>
                <SelectItem value="硕士">硕士</SelectItem>
                <SelectItem value="博士">博士</SelectItem>
              </SelectContent>
            </Select>
            <Select value={expFilter} onValueChange={setExpFilter}>
              <SelectTrigger className="w-24 h-9 text-xs"><SelectValue placeholder="经验" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="全部">全部经验</SelectItem>
                <SelectItem value="经验不限">经验不限</SelectItem>
                <SelectItem value="1-3年">1-3年</SelectItem>
                <SelectItem value="3-5年">3-5年</SelectItem>
                <SelectItem value="5-10年">5-10年</SelectItem>
                <SelectItem value="8-10年">8-10年</SelectItem>
              </SelectContent>
            </Select>
            <Select value={scaleFilter} onValueChange={setScaleFilter}>
              <SelectTrigger className="w-28 h-9 text-xs"><SelectValue placeholder="公司规模" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="全部">全部规模</SelectItem>
                <SelectItem value="0-50人">0-50人</SelectItem>
                <SelectItem value="50-99人">50-99人</SelectItem>
                <SelectItem value="100-499人">100-499人</SelectItem>
                <SelectItem value="500-999人">500-999人</SelectItem>
                <SelectItem value="1000-9999人">1000-9999人</SelectItem>
              </SelectContent>
            </Select>
            <Select value={platformFilter} onValueChange={setPlatformFilter}>
              <SelectTrigger className="w-28 h-9 text-xs"><SelectValue placeholder="招聘平台" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="全部">全部平台</SelectItem>
                <SelectItem value="猎聘">猎聘</SelectItem>
                <SelectItem value="51job">51job</SelectItem>
                <SelectItem value="智联招聘">智联招聘</SelectItem>
                <SelectItem value="BOSS直聘">BOSS直聘</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* 第二行：任务状态显示 + 全局操作按钮 */}
        <div className="flex items-center justify-between pt-1">
          {/* 左侧：数量与任务状态徽章 */}
          <div className="flex items-center gap-4">
            <div className="text-sm font-medium text-muted-foreground border-r pr-4 border-gray-200">
              共 <span className="text-foreground">{filteredJobs.length}</span> 个职位
            </div>
            {globalTaskStatus === "running" && (
              <Badge variant="outline" className="h-9 gap-2 bg-blue-50 text-blue-600 border-blue-200 px-4 shadow-sm animate-pulse">
                <Loader2 className="h-4 w-4 animate-spin" />
                后台任务处理中...
              </Badge>
            )}
            {globalTaskStatus === "completed" && (
              <Badge variant="outline" className="h-9 gap-2 bg-green-50 text-green-600 border-green-200 px-4 shadow-sm">
                ✅ 任务完结
              </Badge>
            )}
          </div>

          {/* 右侧：刷新与录入 */}
          <div className="flex items-center gap-3">
            {refreshed && (
              <span className="text-xs text-green-600 font-medium animate-in fade-in slide-in-from-right-2">✅ 数据已同步</span>
            )}
            <Button
              variant="outline"
              size="sm"
              className="gap-2 h-9 px-4"
              onClick={handleRefresh}
              disabled={isRefreshing}
            >
              <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              {isRefreshing ? '刷新中...' : '刷新列表'}
            </Button>
            <Button
              onClick={onOpenImport}
              size="sm"
              className="gap-2 h-9 px-4 bg-primary shadow-md hover:shadow-lg transition-all"
            >
              <Plus className="h-4 w-4" />
              极速录入
            </Button>
          </div>
        </div>

        {/* 🌟 批量操作栏 */}
        {selectedJobIds.length > 0 && (
          <div className="mt-3 p-3 bg-primary/5 border border-primary/20 rounded-lg flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Checkbox
                checked={selectedJobIds.length === filteredJobs.length}
                onCheckedChange={handleSelectAll}
              />
              <span className="text-sm font-medium text-foreground">
                已选中 {selectedJobIds.length} 个岗位
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="default"
                size="sm"
                className="gap-1.5"
                onClick={handleBatchEvaluate}
                disabled={isProcessing || isBatchRunning}
              >
                {isBatchRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                {isProcessing || isBatchRunning ? '处理中...' : '批量 AI 初步评估'}
              </Button>
              <Button
                variant="default"
                size="sm"
                className="gap-1.5 bg-violet-600 hover:bg-violet-700"
                onClick={handleBatchDeepEvaluate}
                disabled={isProcessing || isBatchRunning}
              >
                {isBatchRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Brain className="h-3.5 w-3.5" />}
                {isProcessing || isBatchRunning ? '处理中...' : '批量 AI 深度评估'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={handleBatchRewrite}
                disabled={isProcessing || isBatchRunning}
              >
                {isBatchRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileEdit className="h-3.5 w-3.5" />}
                {isProcessing || isBatchRunning ? '处理中...' : '批量简历改写'}
              </Button>
              <Button
                variant="default"
                size="sm"
                className="gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white"
                onClick={handleBatchDeepRewrite}
                disabled={isProcessing || isBatchRunning}
              >
                {isBatchRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Bot className="h-3.5 w-3.5" />}
                {isProcessing || isBatchRunning ? '处理中...' : '批量多Agent改写'}
              </Button>
              <Button
                variant="default"
                size="sm"
                className="gap-1.5 bg-pink-600 hover:bg-pink-700"
                onClick={handleBatchDeliver}
                disabled={isProcessing || isBatchRunning}
              >
                {isBatchRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                {isProcessing || isBatchRunning ? '处理中...' : '批量自动投递'}
              </Button>
              <Button
                variant="destructive"
                size="sm"
                className="gap-1.5"
                onClick={() => {
                  if (window.confirm(`⚠️ 危险操作：确定要从系统和飞书中永久删除选中的 ${selectedJobIds.length} 个岗位吗？此操作不可恢复！`)) {
                    onBatchDelete?.(selectedJobIds).then(() => {
                      setSelectedJobIds([])
                    })
                  }
                }}
                disabled={isProcessing || isBatchRunning || !onBatchDelete}
              >
                <Trash2 className="h-3.5 w-3.5" />
                批量删除
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedJobIds([])}
                disabled={isProcessing || isBatchRunning}
              >
                取消选择
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Job List */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-3">
          {sortedJobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onEnterDetail={(selectedJob) => onEnterDetail(selectedJob, sortedJobs)}
              filteredJobs={sortedJobs}
              isSelected={selectedJobIds.includes(job.id)}
              onSelect={(checked) => handleSelectJob(job.id, checked)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

interface JobCardProps {
  job: JobData
  onEnterDetail: (job: JobData) => void
  filteredJobs: JobData[]
  isSelected?: boolean
  onSelect?: (checked: boolean) => void
  processingJob?: string
  liveLogs?: string[]
}

function getGradeStyle(grade: string): { bg: string; text: string; border: string; label: string } {
  const map: Record<string, { bg: string; text: string; border: string; label: string }> = {
    A: { bg: "bg-gradient-to-br from-yellow-400 to-orange-500", text: "text-white", border: "border-yellow-400", label: "A" },
    B: { bg: "bg-gradient-to-br from-emerald-400 to-teal-500", text: "text-white", border: "border-emerald-400", label: "B" },
    C: { bg: "bg-gradient-to-br from-blue-400 to-indigo-500", text: "text-white", border: "border-blue-400", label: "C" },
    D: { bg: "bg-gradient-to-br from-orange-400 to-red-400", text: "text-white", border: "border-orange-400", label: "D" },
    F: { bg: "bg-gradient-to-br from-gray-300 to-gray-400", text: "text-white", border: "border-gray-300", label: "F" },
  }
  return map[grade] ?? { bg: "bg-gray-100", text: "text-gray-400", border: "border-gray-200", label: "?" }
}

function JobCard({ job, onEnterDetail, filteredJobs, isSelected, onSelect, processingJob, liveLogs }: JobCardProps) {
  const gradeStyle = getGradeStyle(job.grade ?? "")
  const dimTotal = (job.roleMatch ?? 0) + (job.skillsAlign ?? 0) + (job.seniority ?? 0) +
    (job.compensation ?? 0) + (job.interviewProb ?? 0) + (job.workMode ?? 0) +
    (job.companyStage ?? 0) + (job.marketFit ?? 0) + (job.growth ?? 0) + (job.timeline ?? 0)

  return (
    <Card className={`p-4 hover:shadow-md transition-all ${
      isSelected ? 'ring-2 ring-primary bg-primary/5' : ''
    }`}>
      <div className="flex items-center gap-4">
        {/* 🌟 Checkbox */}
        {onSelect && (
          <Checkbox
            checked={isSelected}
            onCheckedChange={onSelect}
            onClick={(e) => e.stopPropagation()}
          />
        )}
        {/* Company Logo */}
        <div className="h-12 w-12 rounded-lg bg-muted flex items-center justify-center shrink-0">
          <Building2 className="h-6 w-6 text-muted-foreground" />
        </div>

        {/* Company & Job Info */}
        <div className="min-w-0 w-44">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-foreground truncate text-sm">
              {job.companyName || "未知公司"}
            </span>
            {job.platform && getPlatformBadge(job.platform)}
          </div>
          <div className="flex items-center gap-2">
            <div className="text-sm text-foreground truncate">{job.jobTitle || "未知岗位"}</div>
            {job.followStatus && getFollowStatusBadge(job.followStatus)}
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
            <span className="flex items-center gap-0.5">
              <MapPin className="h-3 w-3" />
              {job.location || "-"}
            </span>
            <span>·</span>
            <span>{job.companyScale || "-"}</span>
          </div>
        </div>

        {/* Salary */}
        <div className="text-base font-bold text-orange-500 shrink-0 w-24 text-center">
          {job.salary || "-"}
        </div>

        {/* Requirements */}
        <div className="flex items-center gap-1.5 shrink-0">
          <Badge variant="secondary" className="text-xs h-5 px-1.5">
            {job.education || "-"}
          </Badge>
          <Badge variant="secondary" className="text-xs h-5 px-1.5">
            {job.experience || "-"}
          </Badge>
        </div>

        {/* A-F Grade Badge */}
        <div className="flex flex-col items-center gap-1 shrink-0">
          <TooltipProvider delayDuration={300}>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className={`h-10 w-10 rounded-xl flex items-center justify-center font-black text-lg shadow-sm cursor-default ${gradeStyle.bg} ${gradeStyle.text}`}>
                  {gradeStyle.label}
                </div>
              </TooltipTrigger>
              {job.aiEvaluationDetail && (
                <TooltipContent side="left" className="max-w-[300px] p-3 bg-white border border-violet-200 shadow-lg">
                  <div className="text-[11px] leading-relaxed text-gray-800 whitespace-pre-line">
                    {job.aiEvaluationDetail.split('\n\n').slice(0, 3).join('\n\n')}
                  </div>
                </TooltipContent>
              )}
            </Tooltip>
          </TooltipProvider>
          {dimTotal > 0 && (
            <span className="text-[10px] text-muted-foreground whitespace-nowrap">
              {dimTotal}/50分
            </span>
          )}
        </div>

        {/* Action Button */}
        <Button
          onClick={() => onEnterDetail(job)}
          size="sm"
          className="gap-1.5 shrink-0"
        >
          进入定制面板
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </Card>
  )
}

function getPlatformBadge(platform: string) {
  const platformConfig: Record<string, { bg: string; text: string }> = {
    "BOSS直聘": { bg: "bg-blue-100", text: "text-blue-700" },
    "猎聘": { bg: "bg-orange-100", text: "text-orange-700" },
    "51job": { bg: "bg-yellow-100", text: "text-yellow-700" },
    "智联招聘": { bg: "bg-green-100", text: "text-green-700" },
  }
  
  const config = platformConfig[platform] || { bg: "bg-gray-100", text: "text-gray-700" }
  
  return (
    <Badge className={`text-[10px] h-4 px-1.5 ${config.bg} ${config.text} hover:${config.bg}`}>
      {platform}
    </Badge>
  )
}

function getFollowStatusBadge(status: string) {
  // 🌟 状态颜色映射表
  const statusConfig: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; className: string }> = {
    "新线索": { variant: "default", className: "bg-blue-100 text-blue-700 hover:bg-blue-100" },
    "不合适": { variant: "secondary", className: "bg-gray-100 text-gray-500 hover:bg-gray-100" },
    "已完成初步评估": { variant: "outline", className: "bg-teal-100 text-teal-700 hover:bg-teal-100 border-teal-300" },
    "已完成深度评估": { variant: "outline", className: "bg-cyan-100 text-cyan-700 hover:bg-cyan-100 border-cyan-300" },
    "简历人工复核": { variant: "outline", className: "bg-orange-100 text-orange-700 hover:bg-orange-100 border-orange-300" },
    "待投递": { variant: "outline", className: "bg-purple-100 text-purple-700 hover:bg-purple-100 border-purple-300" },
    "已投递": { variant: "outline", className: "bg-green-100 text-green-700 hover:bg-green-100 border-green-300" },
    "面试中": { variant: "outline", className: "bg-green-200 text-green-800 hover:bg-green-200 border-green-400" },
    "Offer": { variant: "default", className: "bg-emerald-100 text-emerald-700 hover:bg-emerald-100" },
    "已下架": { variant: "secondary", className: "bg-gray-200 text-gray-600 hover:bg-gray-200" },
    "待人工评估": { variant: "secondary", className: "bg-yellow-100 text-yellow-700 hover:bg-yellow-100" },
    "已拒绝": { variant: "destructive", className: "bg-red-100 text-red-700 hover:bg-red-100" },
  }
  
  const config = statusConfig[status] || { variant: "secondary" as const, className: "bg-gray-100 text-gray-700 hover:bg-gray-100" }
  
  return (
    <Badge variant={config.variant} className={`text-[10px] h-4 px-1.5 ${config.className}`}>
      {status}
    </Badge>
  )
}

