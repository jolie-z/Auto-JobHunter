"use client"

import { useState, useEffect, useRef } from "react"
import { Terminal, X, Minimize2, Maximize2, Send, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface LiveTaskTerminalProps {
  title?: string
  placeholder?: string
  onComplete?: () => void
  onMinimize?: () => void
  onClose?: () => void
  onSseMessage?: (data: LogMessage) => void
  showToolbar?: boolean
  showInternalHeader?: boolean
}

interface LogMessage {
  type: string
  message: string
  timestamp: string
  job_id?: string
  current?: number
  total?: number
  usage?: { prompt: number; completion: number; total: number }
  job_updates?: Record<string, any>
}

let globalChatCache: LogMessage[] = []

export function LiveTaskTerminal({ 
  title = "实时任务控制台", 
  placeholder = "例如: 帮我抓取直聘第3页...",
  onComplete,
  onMinimize,
  onClose,
  onSseMessage,
  showToolbar = false,
  showInternalHeader = true
}: LiveTaskTerminalProps) {
  const [logs, setLogs] = useState<LogMessage[]>(globalChatCache)
  const onSseMessageRef = useRef<((data: LogMessage) => void) | undefined>(onSseMessage)
  useEffect(() => { onSseMessageRef.current = onSseMessage }, [onSseMessage])
  const onCompleteRef = useRef<(() => void) | undefined>(onComplete)
  useEffect(() => { onCompleteRef.current = onComplete }, [onComplete])

  // 🌟 实时同步 logs 到全局缓存，实现跨渲染周期持久化
  useEffect(() => { globalChatCache = logs }, [logs])
  const [isMinimized, setIsMinimized] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  
  // 🌟 智能滚动：追踪用户是否在底部
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const isAutoScrollEnabled = useRef<boolean>(true)

  // 🌟 日志批量缓冲区：防止高频 SSE 消息导致每条都触发 re-render
  const pendingLogsRef = useRef<LogMessage[]>([])

  // 🌟 定时器：每 150ms 将缓冲区的日志批量 flush 到 state（单次 re-render）
  useEffect(() => {
    const interval = setInterval(() => {
      if (pendingLogsRef.current.length > 0) {
        const toFlush = pendingLogsRef.current
        pendingLogsRef.current = []
        setLogs((prev) => [...prev, ...toFlush])
      }
    }, 150)
    return () => clearInterval(interval)
  }, [])

  // ChatOps 独有的交互状态
  const [input, setInput] = useState("")
  const [isExecuting, setIsExecuting] = useState(false)
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  
  // 🌟 生成唯一的 task_id（基于时间戳 + 随机数）
  const generateTaskId = () => {
    return `task_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
  }

  // 🌟 监听全局任务启动事件（来自其他组件，如批量评估按钮）
  useEffect(() => {
    const handleGlobalTask = (e: Event) => {
      const customEvent = e as CustomEvent<{ taskId: string; title?: string }>
      const { taskId, title: eventTitle } = customEvent.detail
      
      console.log('📢 [Terminal] 收到全局任务启动事件:', taskId, eventTitle)
      
      // 1. 强制展开终端
      setIsMinimized(false)
      
      // 2. 设置新的 activeTaskId（会触发下方的 SSE useEffect 自动连接）
      setActiveTaskId(taskId)
      
      // 3. 启用自动滚动
      isAutoScrollEnabled.current = true
      
      // 4. 追加分隔线 + 欢迎日志（保留历史日志，不清屏）
      const dividerLog: LogMessage = {
        type: "info",
        message: `\n---\n🚀 [新任务启动] ${eventTitle || '新任务'} 已启动，正在连接实时日志流...`,
        timestamp: new Date().toLocaleTimeString()
      }
      setLogs((prev) => [...prev, dividerLog])
    }
    
    window.addEventListener('START_GLOBAL_TASK', handleGlobalTask)
    
    return () => {
      window.removeEventListener('START_GLOBAL_TASK', handleGlobalTask)
    }
  }, [])

  // 🌟 智能滚动：仅在用户位于底部时自动滚动
  useEffect(() => {
    if (!isMinimized && isAutoScrollEnabled.current) {
      logsEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }
  }, [logs, isMinimized])

  // 🌟 手动清空日志（同时清空全局缓存和缓冲区）
  const handleClearLogs = () => {
    setLogs([])
    globalChatCache = []
    pendingLogsRef.current = []
  }

  // 🌟 监听滚动事件，判断用户是否在底部
  const handleScroll = () => {
    const container = scrollContainerRef.current
    if (!container) return
    
    const isAtBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 50
    isAutoScrollEnabled.current = isAtBottom
  }

  // SSE 连接逻辑
  useEffect(() => {
    if (!activeTaskId) return

    // 创建 EventSource 连接
    const eventSource = new EventSource(
      `http://127.0.0.1:8000/api/tasks/logs?task_id=${activeTaskId}`
    )
    eventSourceRef.current = eventSource

    eventSource.onopen = () => {
      setIsConnected(true)
      console.log("📡 [SSE] 连接已建立")
    }

    eventSource.onmessage = (event) => {
      try {
        const data: LogMessage = JSON.parse(event.data)
        data.timestamp = new Date().toLocaleTimeString()

        if (data.type !== 'heartbeat') onSseMessageRef.current?.(data)

        // 🌟 推入缓冲区，由 150ms 定时器批量 flush，避免每条消息都触发 re-render
        pendingLogsRef.current.push(data)

        // 处理特殊消息类型（状态变更立即执行，不需要等 flush）
        if (data.type === "end") {
          console.log("🏁 [SSE] 收到结束信号，关闭连接")
          eventSource.close()
          setIsConnected(false)
          setIsExecuting(false)
        } else if (data.type === "complete") {
          console.log("🎉 [SSE] 任务全部完成")
          setTimeout(() => {
            onCompleteRef.current?.()
          }, 2000)
        }
      } catch (error) {
        console.error("❌ [SSE] 解析消息失败:", error)
      }
    }

    eventSource.onerror = (error) => {
      console.error("❌ [SSE] 连接错误:", error)
      setIsConnected(false)
      setIsExecuting(false)
      eventSource.close()
    }

    return () => {
      if (eventSource.readyState !== EventSource.CLOSED) {
        console.log("🔌 [SSE] 组件卸载，关闭连接")
        eventSource.close()
      }
    }
  }, [activeTaskId])

  // 🌟 处理用户输入并调用后端的函数
  const handleCommandSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const commandText = input.trim()
    if (!commandText) return

    // 🌟 核心拦截：如果当前正在执行，且输入的不是“终止”，直接拦截并警告
    if (isExecuting && !["终止", "停止", "结束", "stop", "退出"].includes(commandText)) {
      setLogs((prev) => [...prev, { type: "warning", message: "⚠️ 任务正在执行，请输入 '终止' 来强制停止。", timestamp: new Date().toLocaleTimeString() }])
      setInput("")
      return
    }

    setInput("")
    
    // 🌟 用户主动发送指令，强制启用自动滚动并滚动到底部
    isAutoScrollEnabled.current = true
    
    // 如果不是终止指令，才让终端进入“执行中”状态
    if (!["终止", "停止", "结束", "stop", "退出"].includes(commandText)) {
      setIsExecuting(true)
    }

    // 本地先打印出用户的指令
    setLogs((prev) => [...prev, { type: "info", message: `> ${commandText}`, timestamp: new Date().toLocaleTimeString() }])

    try {
      // 🌟 判断是否为终止类指令
      const isStopCommand = ["终止", "停止", "结束", "stop", "退出"].includes(commandText)
      
      const uniqueTaskId = generateTaskId()
      const res = await fetch("http://127.0.0.1:8000/api/chat/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          command: commandText,
          task_id: uniqueTaskId
        }),
      })
      if (!res.ok) throw new Error("网络请求失败")

      const data = await res.json()
      
      // 🌟 如果是终止指令，只显示返回的 message，不设置 activeTaskId
      if (isStopCommand) {
        if (data.message) {
          setLogs((prev) => [...prev, { 
            type: "success", 
            message: data.message, 
            timestamp: new Date().toLocaleTimeString() 
          }])
        }
        setIsExecuting(false)
      } else {
        // 🌟 正常指令才设置 activeTaskId 建立 SSE 连接
        if (data.task_id) {
          setActiveTaskId(data.task_id) 
        } else {
          setActiveTaskId(uniqueTaskId)
        }
      }
    } catch (error: any) {
      setLogs((prev) => [...prev, { type: "error", message: `启动失败: ${error.message}`, timestamp: new Date().toLocaleTimeString() }])
      setIsExecuting(false)
    }
  }

  // 获取消息图标
  const getMessageIcon = (type: string) => {
    const iconMap: Record<string, string> = {
      connected: "🔗",
      start: "🚀",
      progress: "⏳",
      info: "ℹ️",
      success: "✅",
      error: "❌",
      complete: "🎉",
      warning: "⚠️",
      heartbeat: "💓",
      end: "🏁",
    }
    return iconMap[type] || "📝"
  }

  // 获取气泡样式（根据消息类型）
  const getBubbleStyle = (type: string) => {
    const styleMap: Record<string, string> = {
      connected: "bg-blue-50 text-blue-800 border border-blue-200",
      start: "bg-cyan-50 text-cyan-800 border border-cyan-200",
      progress: "bg-gray-50 text-gray-700 border border-gray-200",
      info: "bg-gray-50 text-gray-700 border border-gray-200",
      success: "bg-green-50 text-green-800 border border-green-200",
      warning: "bg-amber-50 text-amber-800 border border-amber-200",
      error: "bg-red-50 text-red-800 border border-red-200",
      complete: "bg-green-50 text-green-800 border border-green-200",
      end: "bg-gray-100 text-gray-600 border border-gray-300",
    }
    return styleMap[type] || "bg-gray-50 text-gray-700 border border-gray-200"
  }

  return (
    <div
      className={`h-full bg-white transition-all duration-300 flex flex-col overflow-hidden ${
        isMinimized ? "w-16" : "w-full"
      }`}
    >
      {/* Header - 仅在 showToolbar 为 true 且 showInternalHeader 为 true 时显示 */}
      {showInternalHeader && showToolbar && (
        <div className="h-12 px-4 flex items-center justify-between border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white shrink-0">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-gray-700" />
            {!isMinimized && (
              <>
                <span className="text-sm font-medium text-gray-800">
                  {title}
                </span>
                {isConnected && (
                  <span className="flex items-center gap-1 text-xs text-green-600">
                    <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    已连接
                  </span>
                )}
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-gray-500 hover:text-red-600 hover:bg-red-50"
              onClick={handleClearLogs}
              title="清空记录"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
            {onMinimize && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-gray-500 hover:text-gray-700 hover:bg-gray-100"
                onClick={onMinimize}
                title="最小化"
              >
                <Minimize2 className="h-3.5 w-3.5" />
              </Button>
            )}
            {onClose && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-gray-500 hover:text-red-600 hover:bg-red-50"
                onClick={onClose}
                title="关闭"
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        </div>
      )}

      {/* 无工具栏时的简化标题栏 */}
      {showInternalHeader && !showToolbar && (
        <div className="h-10 px-4 flex items-center border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white shrink-0">
          <div className="flex items-center gap-2">
            <Terminal className="h-3.5 w-3.5 text-gray-700" />
            <span className="text-sm font-medium text-gray-800">
              {title}
            </span>
            {isConnected && (
              <span className="flex items-center gap-1 text-xs text-green-600">
                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                已连接
              </span>
            )}
          </div>
        </div>
      )}

      {/* Terminal Body */}
      {!isMinimized && (
        <div className="flex-1 min-h-0 flex flex-col bg-gray-50">
          
          {/* 上半部分：日志滚动区（气泡化） */}
          <div 
            ref={scrollContainerRef}
            onScroll={handleScroll}
            className="flex-1 min-h-0 overflow-y-auto p-4 space-y-2"
          >
            {logs.length === 0 ? (
              <div className="text-gray-400 text-sm text-center mt-8">
                等待任务日志或在下方输入指令...
              </div>
            ) : (
              <div className="space-y-1">
                {logs.map((log, index) => {
                  if (log.type === "heartbeat") return null

                  const isUserCommand = log.message?.startsWith("> ") ?? false

                  if (isUserCommand) {
                    // 用户指令气泡：右侧对齐，蓝色
                    const displayText = log.message.slice(2)
                    return (
                      <div key={index} className="flex w-full justify-end mb-4">
                        <div className="bg-blue-500 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 shadow-sm max-w-[80%]">
                          <div className="text-sm leading-relaxed break-words font-medium">
                            {displayText}
                          </div>
                          <div className="text-right mt-1">
                            <span className="text-xs text-blue-100 opacity-80">{log.timestamp}</span>
                          </div>
                        </div>
                      </div>
                    )
                  }

                  // [诊断] 消息：紫色样式 + 保留换行
                  const isDiagnosis = log.message?.startsWith("[诊断]")
                  if (isDiagnosis) {
                    return (
                      <div key={index} className="flex w-full justify-start mb-2">
                        <div className="rounded-2xl rounded-tl-sm px-3 py-2.5 max-w-[95%] shadow-sm bg-violet-50 text-violet-900 border border-violet-200">
                          <div className="flex items-start gap-2">
                            <span className="text-base shrink-0 leading-none mt-0.5">🔬</span>
                            <div className="flex-1 min-w-0">
                              <div className="text-xs leading-relaxed break-words whitespace-pre-wrap font-mono">
                                {log.message}
                              </div>
                              <div className="mt-1">
                                <span className="text-xs opacity-50">{log.timestamp}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  }

                  // 系统日志气泡：左侧对齐，保留状态色
                  return (
                    <div key={index} className="flex w-full justify-start mb-2">
                      <div className={`rounded-2xl rounded-tl-sm px-3 py-2.5 max-w-[85%] shadow-sm ${getBubbleStyle(log.type)}`}>
                        <div className="flex items-start gap-2">
                          <span className="text-base shrink-0 leading-none mt-0.5">{getMessageIcon(log.type)}</span>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm leading-relaxed break-words overflow-x-auto">
                              <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={{
                                  table: ({node, ...props}) => (
                                    <div className="overflow-x-auto my-3 rounded-lg border border-gray-200 shadow-sm">
                                      <table className="min-w-full divide-y divide-gray-200 text-xs text-left whitespace-nowrap" {...props} />
                                    </div>
                                  ),
                                  thead: ({node, ...props}) => <thead className="bg-gray-100/80 text-gray-700 font-semibold" {...props} />,
                                  th: ({node, ...props}) => <th className="px-3 py-2" {...props} />,
                                  tbody: ({node, ...props}) => <tbody className="divide-y divide-gray-100 bg-white" {...props} />,
                                  tr: ({node, ...props}) => <tr className="hover:bg-blue-50/50 transition-colors" {...props} />,
                                  td: ({node, ...props}) => <td className="px-3 py-2" {...props} />,
                                  p: ({node, ...props}) => <p className="mb-1 last:mb-0" {...props} />
                                }}
                              >
                                {log.message}
                              </ReactMarkdown>
                            </div>
                            <div className="flex items-center gap-2 mt-1 flex-wrap">
                              <span className="text-xs opacity-60">{log.timestamp}</span>
                              {log.current && log.total && (
                                <span className="text-xs opacity-60">({log.current}/{log.total})</span>
                              )}
                              {log.usage && log.usage.total > 0 && (
                                <span className="text-xs opacity-50 font-mono">
                                  · Token: 提示 {log.usage.prompt} / 补全 {log.usage.completion} / 总计 {log.usage.total}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>

          {/* 下半部分：命令行输入区（现代化） */}
          <div className="p-4 border-t border-gray-200 bg-white shrink-0">
            <form onSubmit={handleCommandSubmit} className="flex items-center gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={isExecuting ? "执行中，输入 '终止' 可强行切断..." : placeholder}
                className="flex-1 bg-gray-100 text-gray-800 text-sm px-4 py-2.5 rounded-xl outline-none focus:ring-2 focus:ring-gray-300 placeholder:text-gray-400 transition-all"
              />
              <Button 
                type="submit" 
                disabled={!input.trim()} 
                size="sm" 
                className="h-10 px-4 bg-gray-800 text-white hover:bg-gray-700 disabled:bg-gray-300 disabled:text-gray-500 rounded-xl transition-all"
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>

        </div>
      )}
    </div>
  )
}