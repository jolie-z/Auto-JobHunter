"use client"

import { useState, useRef, useEffect } from "react"
import { Bot, X, Loader2, Send, ChevronDown, Copy, Check, MessageSquareQuote, Highlighter } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

interface FloatingCopilotWidgetProps {
  job: any | null
  selectedText: string
}

export function FloatingCopilotWidget({ job, selectedText }: FloatingCopilotWidgetProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
  const [instruction, setInstruction] = useState("")
  const [isChatLoading, setIsChatLoading] = useState(false)
  
  // 🌟 拖拽状态
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })
  const panelRef = useRef<HTMLDivElement>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const [selectionText, setSelectionText] = useState("")
  const [selectionPosition, setSelectionPosition] = useState<{ top: number; left: number } | null>(null)
  const selectionToolbarRef = useRef<HTMLDivElement>(null)
  const [highlightedTexts, setHighlightedTexts] = useState<string[]>([])

  // 🌟 初始化位置（右下角）
  useEffect(() => {
    if (typeof window !== "undefined") {
      setPosition({
        x: window.innerWidth - 450 - 24, // 距离右边 24px
        y: window.innerHeight - 600 - 24, // 距离底部 24px
      })
    }
  }, [])

  // 🌟 拖拽逻辑
  const handleMouseDown = (e: React.MouseEvent) => {
    if (!panelRef.current) return
    setIsDragging(true)
    setDragOffset({
      x: e.clientX - position.x,
      y: e.clientY - position.y,
    })
  }

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return
      
      const newX = e.clientX - dragOffset.x
      const newY = e.clientY - dragOffset.y
      
      // 🌟 边界限制
      const maxX = window.innerWidth - 450
      const maxY = window.innerHeight - 600
      
      setPosition({
        x: Math.max(0, Math.min(newX, maxX)),
        y: Math.max(0, Math.min(newY, maxY)),
      })
    }

    const handleMouseUp = () => {
      setIsDragging(false)
    }

    if (isDragging) {
      document.addEventListener("mousemove", handleMouseMove)
      document.addEventListener("mouseup", handleMouseUp)
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove)
      document.removeEventListener("mouseup", handleMouseUp)
    }
  }, [isDragging, dragOffset])

  // 🌟 打开 Copilot（自动填入选中文字）
  const handleOpenCopilot = () => {
    setIsOpen(true)
    if (selectedText) {
      setInstruction(selectedText)
    }
  }

  // 🌟 发送消息到后端
  const handleSendMessage = async () => {
    const userQuestion = instruction.trim()
    if (!userQuestion || !job) return

    const newUserMessage: ChatMessage = { role: "user", content: userQuestion }
    setChatHistory((prev) => [...prev, newUserMessage])
    setInstruction("")
    setIsChatLoading(true)

    try {
      // 🌟 组装上下文：从当前 job 对象中提取所有关键信息
      const evaluationReport = [
        job?.dreamPicture ? `【理想画像与能力信号】\n${job.dreamPicture}` : "",
        job?.atsAbilityAnalysis ? `【核心能力词典】\n${job.atsAbilityAnalysis}` : "",
        job?.strongFitAssessment ? `【高杠杆匹配点】\n${job.strongFitAssessment}` : "",
        job?.riskRedFlags ? `【致命硬伤与毒点】\n${job.riskRedFlags}` : "",
        job?.deepActionPlan ? `【破局行动计划】\n${job.deepActionPlan}` : "",
      ]
        .filter(Boolean)
        .join("\n\n")

      const context = {
        jd_text: job?.jobDescription || job?.jobDetail || "",
        evaluation_report: evaluationReport,
        ai_resume_json: job?.aiRewriteJson || "",
        human_refined_resume: job?.manualRefinedResume || "",
      }

      const history = chatHistory.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }))

      const response = await fetch("http://127.0.0.1:8000/copilot_chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_question: userQuestion,
          context,
          history,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || "请求失败")
      }

      const aiMessage: ChatMessage = {
        role: "assistant",
        content: data.reply || "抱歉，我没有理解您的问题。",
      }
      setChatHistory((prev) => [...prev, aiMessage])
    } catch (error) {
      console.error("Copilot Chat 错误:", error)
      const errorMessage: ChatMessage = {
        role: "assistant",
        content: `❌ 抱歉，服务暂时不可用：${error instanceof Error ? error.message : "未知错误"}`,
      }
      setChatHistory((prev) => [...prev, errorMessage])
    } finally {
      setIsChatLoading(false)
    }
  }

  // 🌟 localStorage 持久化：按岗位读取聊天记录
  useEffect(() => {
    if (!job?.id) {
      setChatHistory([])
      return
    }
    try {
      const saved = localStorage.getItem(`copilot_chat_${job.id}`)
      setChatHistory(saved ? (JSON.parse(saved) as ChatMessage[]) : [])
    } catch {
      setChatHistory([])
    }
  }, [job?.id])

  // 🌟 localStorage 持久化：聊天记录更新时同步写入
  useEffect(() => {
    if (!job?.id) return
    try {
      localStorage.setItem(`copilot_chat_${job.id}`, JSON.stringify(chatHistory))
    } catch {
      // ignore storage errors
    }
  }, [chatHistory, job?.id])

  // 🌟 自动滚动到对话底部（chatHistory 更新时）
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [chatHistory])

  // 🌟 自动滚动到对话底部（isOpen 变为 true 时）
  useEffect(() => {
    if (isOpen) {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }
  }, [isOpen])

  // 🌟 监听消息区域滚动，向上超过 150px 时显示回到底部按鈕
  useEffect(() => {
    if (!isOpen) return
    const el = scrollContainerRef.current
    if (!el) return
    const handleScroll = () => {
      const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
      setShowScrollBtn(distFromBottom > 150)
    }
    el.addEventListener("scroll", handleScroll)
    return () => el.removeEventListener("scroll", handleScroll)
  }, [isOpen])

  // 🌟 划词弹出工具栏
  const handleChatMouseUp = () => {
    const selection = window.getSelection()
    if (!selection || selection.isCollapsed) return
    const text = selection.toString().trim()
    if (!text) return
    const range = selection.getRangeAt(0)
    const rect = range.getBoundingClientRect()
    setSelectionText(text)
    setSelectionPosition({
      top: rect.top - 44,
      left: (rect.left + rect.right) / 2,
    })
  }

  // 🌟 点击浮窗外，隐藏选中工具栏
  useEffect(() => {
    const handleDocMouseDown = (e: MouseEvent) => {
      if (selectionToolbarRef.current && !selectionToolbarRef.current.contains(e.target as Node)) {
        setSelectionPosition(null)
        setSelectionText("")
      }
    }
    document.addEventListener("mousedown", handleDocMouseDown)
    return () => document.removeEventListener("mousedown", handleDocMouseDown)
  }, [])

  // 🌟 高亮渲染：将 content 中匹配 highlightedTexts 的片段用 <mark> 包裹（React 元素，无 XSS 风险）
  const renderMessageWithHighlights = (content: string): React.ReactNode => {
    if (highlightedTexts.length === 0) return content
    const escaped = highlightedTexts.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    const pattern = new RegExp(`(${escaped.join("|")})`, "g")
    const parts = content.split(pattern)
    return parts.map((part, i) =>
      highlightedTexts.includes(part) ? (
        <mark key={i} className="bg-yellow-200 dark:bg-yellow-900/50 rounded-sm px-0.5">
          {part}
        </mark>
      ) : (
        part
      )
    )
  }

  // 🌟 Enter 发送，Shift+Enter 换行
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <>
      {/* 🌟 Trigger Button（关闭状态） */}
      {!isOpen && (
        <button
          onClick={handleOpenCopilot}
          className="
            fixed bottom-6 right-6 z-50
            w-14 h-14 rounded-full
            bg-gradient-to-br from-primary to-primary/80
            shadow-lg hover:shadow-2xl
            flex items-center justify-center
            transition-all duration-300 hover:scale-110
            group
          "
          aria-label="打开 AI Copilot"
        >
          <Bot className="h-7 w-7 text-primary-foreground group-hover:scale-110 transition-transform" />
        </button>
      )}

      {/* 🌟 Draggable Chat Panel（打开状态） */}
      {isOpen && (
        <div
          ref={panelRef}
          className="fixed z-50 flex flex-col bg-card border border-border rounded-xl shadow-2xl"
          style={{
            left: `${position.x}px`,
            top: `${position.y}px`,
            width: "450px",
            height: "600px",
            minWidth: "280px",
            minHeight: "350px",
            maxWidth: "800px",
            maxHeight: "90vh",
            resize: "both",
            overflow: "hidden",
          }}
        >
          {/* Header（可拖拽把手） */}
          <div
            className={`
              px-4 py-3 border-b border-border bg-muted/30 
              flex items-center justify-between
              ${isDragging ? "cursor-grabbing" : "cursor-grab"}
              select-none
            `}
            onMouseDown={handleMouseDown}
          >
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-primary" />
              <span className="font-semibold text-sm">AI Job Copilot</span>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setIsOpen(false)}
              className="hover:bg-destructive/10"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Body（对话历史） */}
          <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-4 space-y-3 relative" onMouseUp={handleChatMouseUp}>
            {chatHistory.length === 0 && (
              <div className="text-center text-[11px] text-muted-foreground py-8">
                <p className="mb-2">💬 你的专属求职 Copilot 已就绪</p>
                <p className="text-[10px] leading-relaxed">
                  可以问我关于 JD 解读、简历改写逻辑、面试防守策略等问题
                </p>
              </div>
            )}
            {chatHistory.map((msg, index) => (
              <div
                key={index}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-lg px-3 py-2 text-[11px] leading-relaxed ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-foreground border border-border"
                  }`}
                >
                  <div className="whitespace-pre-wrap break-words">{renderMessageWithHighlights(msg.content)}</div>
                  {msg.role !== "user" && (
                    <div className="flex justify-end mt-1.5">
                      <button
                        className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-muted/60 rounded transition-colors"
                        onClick={() => {
                          navigator.clipboard.writeText(msg.content)
                          setCopiedIndex(index)
                          setTimeout(() => setCopiedIndex(null), 2000)
                        }}
                      >
                        {copiedIndex === index ? (
                          <Check className="h-3 w-3 text-green-500" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isChatLoading && (
              <div className="flex justify-start">
                <div className="max-w-[85%] rounded-lg px-3 py-2 text-[11px] bg-muted text-muted-foreground border border-border flex items-center gap-2">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Copilot 正在思考...
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
            {showScrollBtn && (
              <div className="sticky bottom-0 flex justify-center py-1">
                <button
                  onClick={() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" })}
                  className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/90 text-primary-foreground shadow-lg hover:bg-primary transition-colors"
                  aria-label="滚动到底部"
                >
                  <ChevronDown className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>

          {/* Footer（输入区域） */}
          <div className="p-4 border-t border-border bg-muted/10">
            {selectedText && (
              <div className="text-[10px] text-muted-foreground mb-2 p-2 bg-amber-50 dark:bg-amber-950/20 rounded border border-amber-200 dark:border-amber-800 truncate">
                📌 已选中文字：{selectedText.slice(0, 50)}{selectedText.length > 50 ? "..." : ""}
              </div>
            )}
            <div className="flex gap-2 items-end">
              <Textarea
                className="flex-1 min-h-[60px] max-h-[400px] text-xs resize-y"
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="对岗位 JD、改写逻辑或评估报告有疑问？直接问我...

例如：'这个岗位最看重什么？' / '为什么把这个项目前置？'"
                disabled={isChatLoading}
              />
              <Button
                className="px-3 gap-1.5 shrink-0"
                onClick={handleSendMessage}
                disabled={isChatLoading || !instruction.trim()}
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}
      {/* 🌟 划词浮动工具栏 */}
      {selectionPosition && (
        <div
          ref={selectionToolbarRef}
          className="fixed z-[100] flex items-center gap-1 px-2 py-1.5 bg-zinc-900 rounded-lg shadow-xl"
          style={{
            top: `${selectionPosition.top}px`,
            left: `${selectionPosition.left}px`,
            transform: "translateX(-50%)",
          }}
        >
          <button
            className="flex items-center gap-1 px-2 py-1 text-[11px] text-white/90 hover:bg-white/10 rounded-md transition-colors"
            onClick={() => {
              setInstruction((prev) => (prev ? prev + "\n\n" : "") + `关于这段内容：\n> ${selectionText}\n\n我的问题是：`)
              setSelectionPosition(null)
              setSelectionText("")
              window.getSelection()?.removeAllRanges()
            }}
          >
            <MessageSquareQuote className="h-3.5 w-3.5" />
            追问
          </button>
          <button
            className="flex items-center gap-1 px-2 py-1 text-[11px] text-white/90 hover:bg-white/10 rounded-md transition-colors"
            onClick={() => {
              if (selectionText) setHighlightedTexts((prev) => prev.includes(selectionText) ? prev : [...prev, selectionText])
              setSelectionPosition(null)
              setSelectionText("")
              window.getSelection()?.removeAllRanges()
            }}
          >
            <Highlighter className="h-3.5 w-3.5" />
            高亮
          </button>
        </div>
      )}
    </>
  )
}
