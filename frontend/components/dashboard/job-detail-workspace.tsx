"use client"

import { useCallback, useEffect, useMemo, useState, useRef } from "react"
import type { ReactNode } from "react"
import {
  ArrowLeft,
  Save,
  Image,
  FileText,
  ExternalLink,
  Copy,
  Sparkles,
  Search,
  Replace,
  Bold,
  ArrowUp,
  ArrowDown,
  GripVertical,
  Loader2,
  ChevronLeft,
  ChevronRight,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import type { JobData } from "@/app/page"
import { FloatingCopilotWidget } from "@/components/dashboard/floating-copilot-widget"

// 状态颜色映射表
const getStatusBadgeColor = (status: string): string => {
  const colorMap: Record<string, string> = {
    "新线索": "bg-blue-100 text-blue-800 hover:bg-blue-100",
    "不合适": "bg-red-100 text-red-800 hover:bg-red-100",
    "已完成初步评估": "bg-teal-100 text-teal-800 hover:bg-teal-100",
    "已完成深度评估": "bg-cyan-100 text-cyan-800 hover:bg-cyan-100",
    "简历人工复核": "bg-orange-100 text-orange-800 hover:bg-orange-100",
    "待投递": "bg-indigo-100 text-indigo-800 hover:bg-indigo-100",
    "已投递": "bg-purple-100 text-purple-800 hover:bg-purple-100",
    "面试中": "bg-green-100 text-green-800 hover:bg-green-100",
    "Offer": "bg-emerald-100 text-emerald-800 hover:bg-emerald-100",
    "已下架": "bg-gray-200 text-gray-600 hover:bg-gray-200",
    "待人工复核": "bg-yellow-100 text-yellow-800 hover:bg-yellow-100",
    "准备投递": "bg-cyan-100 text-cyan-800 hover:bg-cyan-100",
    "已拒绝": "bg-gray-100 text-gray-800 hover:bg-gray-100",
  }
  // 如果状态不在映射表中，返回默认的紫色
  return colorMap[status] || "bg-purple-100 text-purple-800 hover:bg-purple-100"
}

interface JobDetailWorkspaceProps {
  job: JobData
  onUpdateJob: (job: JobData | null, action?: 'remove') => void
  onBack: () => void
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
  dynamicStatuses: string[]
  onRefreshJobs?: () => Promise<void>  // 🌟 可选：用于刷新全局数据
}

interface ResumeSection {
  id: string
  title: string
  content: string
}

interface ResumeData {
  header: {
    name: string
    contact: string
    intention: string
  }
  sections: ResumeSection[]
}

interface EditableSectionProps {
  section: ResumeSection
  isMatched: boolean
  onSelectText: (text: string, sectionId: string) => void
  onCommit: (nextSection: ResumeSection) => void
  onDragStart: (sectionId: string) => void
  onDropTo: (targetSectionId: string) => void
  onMoveUp: () => void
  onMoveDown: () => void
  findText: string
  currentMatchIndex: number
  onRegisterMatch: (id: string) => number
}

// 🌟 LinkifyText 组件：自动将文本中的 URL 转换为可点击的超链接
function LinkifyText({ text }: { text: string }) {
  // URL 正则表达式：匹配 http:// 或 https:// 开头的链接
  const urlRegex = /(https?:\/\/[^\s]+)/g
  const parts = text.split(urlRegex)

  return (
    <>
      {parts.map((part, index) => {
        // 如果是 URL，渲染为超链接
        if (part.match(urlRegex)) {
          return (
            <a
              key={index}
              href={part}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {part}
            </a>
          )
        }
        // 普通文本直接返回
        return <span key={index}>{part}</span>
      })}
    </>
  )
}

// 🌟 HighlightText 组件：使用正则切割实现字级别高亮
function HighlightText({ 
  text, 
  searchKeyword, 
  currentMatchIndex,
  onRegisterMatch 
}: { 
  text: string
  searchKeyword: string
  currentMatchIndex: number
  onRegisterMatch: (id: string) => number
}) {
  if (!searchKeyword.trim()) {
    // 🌟 即使没有搜索关键词，也应用 URL 超链接转换
    return <LinkifyText text={text} />
  }

  const regex = new RegExp(`(${searchKeyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  const parts = text.split(regex)

  return (
    <>
      {parts.map((part, index) => {
        if (part.toLowerCase() === searchKeyword.toLowerCase()) {
          // 匹配的关键词，注册并获取全局索引
          const matchId = `search-match-${index}-${part}`
          const globalIndex = onRegisterMatch(matchId)
          const isActive = globalIndex === currentMatchIndex
          
          return (
            <mark 
              key={`${index}-${part}`}
              id={matchId}
              className={isActive 
                ? 'bg-orange-500 text-white font-bold px-0.5 rounded' 
                : 'bg-yellow-200 text-black px-0.5 rounded'
              }
            >
              {part}
            </mark>
          )
        }
        // 普通文本也应用 URL 超链接转换
        return <LinkifyText key={index} text={part} />
      })}
    </>
  )
}

// 🌟 行内 Markdown 渲染：解析 **bold** 片段
function renderInlineMarkdown(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*\n]+\*\*)/g)
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={i} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      )
    }
    return <span key={i}>{part}</span>
  })
}

// 🌟 Markdown 简历预览组件：支持加粗、• 列表、多层缩进，对标 Copilot 排版
function MdPreview({ text }: { text: string }) {
  if (!text.trim()) {
    return (
      <span className="text-muted-foreground/50 italic text-[10px] select-none">
        点击编辑内容…
      </span>
    )
  }

  const lines = text.split("\n")
  const nodes: ReactNode[] = []
  let listBuffer: { content: string; indent: number }[] = []

  const flushList = (key: string) => {
    if (listBuffer.length === 0) return
    const firstIndent = listBuffer[0].indent
    nodes.push(
      <ul key={key} className={`space-y-0.5 my-0.5 ${firstIndent >= 4 ? "pl-6" : "pl-3"}`}>
        {listBuffer.map((item, i) => (
          <li key={i} className="flex gap-1.5 leading-relaxed">
            <span className="shrink-0 text-muted-foreground select-none">•</span>
            <span className="flex-1">{renderInlineMarkdown(item.content)}</span>
          </li>
        ))}
      </ul>
    )
    listBuffer = []
  }

  lines.forEach((rawLine, idx) => {
    const trimmed = rawLine.trimStart()
    const indent = rawLine.length - trimmed.length
    const bulletMatch = trimmed.match(/^[•\-]\s+(.*)$/)

    if (bulletMatch) {
      listBuffer.push({ content: bulletMatch[1], indent })
      return
    }

    flushList(`list-${idx}`)

    if (trimmed === "") {
      if (nodes.length > 0) nodes.push(<div key={`gap-${idx}`} className="h-1" />)
      return
    }

    if (trimmed.startsWith("## ")) {
      nodes.push(
        <p key={`h2-${idx}`} className="font-semibold text-[11px] leading-relaxed mt-1.5">
          {renderInlineMarkdown(trimmed.slice(3))}
        </p>
      )
      return
    }

    const paddingClass = indent >= 4 ? "pl-5" : indent >= 2 ? "pl-3" : ""
    nodes.push(
      <p key={`p-${idx}`} className={`text-[11px] leading-relaxed ${paddingClass}`}>
        {renderInlineMarkdown(rawLine)}
      </p>
    )
  })

  flushList("list-final")
  return <div className="text-[11px] text-foreground">{nodes}</div>
}

const DEFAULT_RESUME: ResumeData = {
  header: {
    name: "候选人",
    contact: "手机号 | 邮箱",
    intention: "求职意向：AI产品经理",
  },
  sections: [
    { id: "summary", title: "个人总结", content: "请在这里填写个人总结。" },
    { id: "skills", title: "专业技能", content: "请在这里填写专业技能。" },
    { id: "project", title: "项目经历", content: "请在这里填写项目经历。" },
    { id: "work", title: "工作经历", content: "请在这里填写工作经历。" },
    { id: "education", title: "教育背景", content: "请在这里填写教育背景。" },
  ],
}

interface RewriteAnnotItem {
  subtitle: string
  rationale: string
}

interface RewriteAnnotGroup {
  section: "project" | "work"
  title: string
  items: RewriteAnnotItem[]
}

// 🌟 全局极其坚固的 JSON 解析器
function safeParseJSON(raw: string | null | undefined): any {
  if (!raw) return null;
  const t = String(raw).trim();
  if (!t) return null;

  // 🌟 新增：如果字符串显然不是 JSON（不是以 { 或 [ 开头），直接返回原字符串
  // 这样可以防止 JSON.parse 碰到 Markdown 的 # 号报错
  if (!t.startsWith('{') && !t.startsWith('[') && !t.startsWith('`')) {
    return t; 
  }

  try {
    return JSON.parse(t);
  } catch (e) {
    const backticks = "\x60\x60\x60";
    const r1 = new RegExp("^" + backticks + "(?:json)?\\s*", "i");
    const r2 = new RegExp("\\s*" + backticks + "\\s*$");
    const stripped = t.replace(r1, "").replace(r2, "").trim();
    try {
      return JSON.parse(stripped);
    } catch (e2) {
      // 🌟 核心改进：如果 JSON 解析彻底失败，且包含 # 号，说明它可能是纯文本/Markdown
      if (t.includes('#')) {
        return t; 
      }
      console.warn("❌ JSON解析彻底失败:", e2);
      return null;
    }
  }
}

function parseAiRewriteAnnotations(jsonStr: string): {
  groups: RewriteAnnotGroup[]
  hasAny: boolean
} {
  const data = safeParseJSON(jsonStr)

  // 🚀 前端拦截解析：如果识别为纯 Markdown 字符串，执行正则定点提取
  if (typeof data === 'string') {
    const items: RewriteAnnotItem[] = [];

    // 1. 提取正文中所有散落的 Copilot 优化思路 ( > 💡 Copilot 优化思路：... )
    const rationaleRegex = /(?:\n|^)>\s*💡\s*Copilot\s*优化思路[：:]?\s*([^\n]+)/gi;
    let match;
    let rationaleCount = 1;
    while ((match = rationaleRegex.exec(data)) !== null) {
      if (match[1].trim()) {
        items.push({ subtitle: `优化点 ${rationaleCount++}`, rationale: match[1].trim() });
      }
    }

    // 2. 提取末尾的待办与补充清单
    const todoRegex = /(?:\n|^)#\s*待办与补充清单\s*\n([\s\S]*?)(?=(?:\n#\s)|$)/i;
    const todoMatch = data.match(todoRegex);
    if (todoMatch && todoMatch[1].trim()) {
      const cleanTodo = todoMatch[1].trim().replace(/^\s*[-*•]\s*/gm, '• ');
      items.push({ subtitle: "待办与数据补充", rationale: cleanTodo });
    }

    // 🌟 新增 3：提取顶部混合的 JSON 说明块
    const jsonBlockMatch = data.match(/(?:\n|^)\s*(\{[\s\S]*?\})\s*(?=\n#|\n##)/);
    if (jsonBlockMatch) {
      try {
        const parsedData = JSON.parse(jsonBlockMatch[1]);
        if (parsedData.missing_data_requests && Array.isArray(parsedData.missing_data_requests)) {
          parsedData.missing_data_requests.forEach((req: any) => {
            items.push({ subtitle: `📝 待补充 (${req.field})`, rationale: req.question });
          });
        }
        if (parsedData.rewrite_rationale) {
          Object.entries(parsedData.rewrite_rationale).forEach(([key, val]) => {
            items.push({ subtitle: `💡 改写思路 (${key})`, rationale: String(val) });
          });
        }
      } catch(e) {
        console.warn("解析前置JSON说明失败", e);
      }
    }

    // 🌟 新增 4：提取底部的重构说明
    const bottomNoteMatch = data.match(/(?:\n|^)(?:---|___)?\s*\n?\s*\**重构说明\**[：:]\s*([\s\S]*)$/i);
    if (bottomNoteMatch && bottomNoteMatch[1].trim()) {
      items.push({ subtitle: "📋 整体重构说明", rationale: bottomNoteMatch[1].trim() });
    }

    // 如果提取到了任何一条，就组装成指定的结构返回
    if (items.length > 0) {
      return {
        groups: [{
          section: "project",
          title: "AI 整体改写说明",
          items: items
        }],
        hasAny: true
      };
    }
    
    return { groups: [], hasAny: false };
  }

  // ... (保留后面的原对象解析逻辑不变)


  if (!data || typeof data !== "object") {
    return { groups: [], hasAny: false }
  }

  const groups: RewriteAnnotGroup[] = []
  let hasAny = false

  // 🌟 新结构：projects 的 rewrite_rationale 在项目对象的顶层
  if (Array.isArray(data.projects)) {
    for (const p of data.projects) {
      if (!p || typeof p !== "object") continue
      const rec = p as Record<string, unknown>
      const titleRaw = rec.project_name
      const title = titleRaw != null && String(titleRaw).trim() ? String(titleRaw).trim() : "未命名项目"
      const items: RewriteAnnotItem[] = []
      
      // 🌟 直接从项目对象提取 rewrite_rationale
      const rat = rec.rewrite_rationale
      if (rat != null && String(rat).trim()) {
        hasAny = true
        items.push({ subtitle: "全局重构", rationale: String(rat).trim() })
      } else {
        // 兼容旧结构：从 star_a_actions 中提取
        const actions = rec.star_a_actions
        if (Array.isArray(actions)) {
          for (const act of actions) {
            if (!act || typeof act !== "object") continue
            const a = act as Record<string, unknown>
            const oldRat = a.rewrite_rationale
            if (oldRat == null || !String(oldRat).trim()) continue
            hasAny = true
            const sub = a.subtitle != null ? String(a.subtitle).trim() : ""
            items.push({ subtitle: sub, rationale: String(oldRat).trim() })
          }
        }
      }
      
      if (items.length > 0) {
        groups.push({ section: "project", title, items })
      }
    }
  }

  // 🌟 新结构：work_experience 的 rewrite_rationale 在工作对象的顶层
  if (Array.isArray(data.work_experience)) {
    for (const w of data.work_experience) {
      if (!w || typeof w !== "object") continue
      const rec = w as Record<string, unknown>
      const company = rec.company_name != null ? String(rec.company_name).trim() : rec.company != null ? String(rec.company).trim() : ""
      const title = company || "未命名公司"
      const items: RewriteAnnotItem[] = []
      
      // 🌟 直接从工作对象提取 rewrite_rationale
      const rat = rec.rewrite_rationale
      if (rat != null && String(rat).trim()) {
        hasAny = true
        items.push({ subtitle: "全局重构", rationale: String(rat).trim() })
      } else {
        // 兼容旧结构：从 actions 中提取
        const actions = rec.actions
        if (Array.isArray(actions)) {
          for (const act of actions) {
            if (!act || typeof act !== "object") continue
            const a = act as Record<string, unknown>
            const oldRat = a.rewrite_rationale
            if (oldRat == null || !String(oldRat).trim()) continue
            hasAny = true
            const sub = a.subtitle != null ? String(a.subtitle).trim() : ""
            items.push({ subtitle: sub, rationale: String(oldRat).trim() })
          }
        }
      }
      
      if (items.length > 0) {
        groups.push({ section: "work", title, items })
      }
    }
  }

  return { groups, hasAny }
}

function transformJsonToResumeData(data: any): ResumeData {
  if (!data || typeof data !== "object") return DEFAULT_RESUME

  if (data.header && typeof data.header === "object" && Array.isArray(data.sections) && data.sections.length > 0) {
    const header = data.header
    const sections: ResumeSection[] = data.sections.map((s: any, index: number) => ({
      id: String(s?.id ?? `section-${index}`),
      title: String(s?.title ?? `模块${index + 1}`),
      content: String(s?.content ?? ""),
    }))
    return {
      header: {
        name: String(header.name ?? DEFAULT_RESUME.header.name),
        contact: String(header.contact ?? DEFAULT_RESUME.header.contact),
        intention: String(header.intention ?? DEFAULT_RESUME.header.intention),
      },
      sections,
    }
  }

  const pi = data.personal_info ?? {}
  const phone = String(pi.phone ?? pi.mobile ?? "").trim()
  const email = String(pi.email ?? "").trim()
  let contact = ""
  if (typeof pi.contact === "string" && pi.contact.trim()) {
    contact = pi.contact.trim()
  } else if (phone || email) {
    contact = [phone, email].filter(Boolean).join(" | ")
  } else {
    contact = DEFAULT_RESUME.header.contact
  }

  const header = {
    name: String(pi.name ?? DEFAULT_RESUME.header.name),
    contact,
    intention: DEFAULT_RESUME.header.intention,
  }

  const summaryContent = typeof data.summary === "string" ? data.summary : ""

  let skillsContent = ""
  if (Array.isArray(data.skills)) {
    const blocks: string[] = []
    for (const sk of data.skills) {
      const category = sk?.category != null ? String(sk.category).trim() : ""
      const descriptions = Array.isArray(sk?.descriptions) ? sk.descriptions : []
      const body = descriptions.map((d: any) => String(d ?? "").trim()).filter(Boolean).join("\n")
      
      if (category && body) {
        blocks.push(`**【${category}】**\n${body}`)
      } else if (category) {
        blocks.push(`**【${category}】**`)
      } else if (body) {
        blocks.push(body)
      }
    }
    skillsContent = blocks.join("\n\n")
  }

  let projectContent = ""
  if (Array.isArray(data.projects)) {
    const projectBlocks: string[] = []
    for (const p of data.projects) {
      const projectName = p?.project_name != null ? String(p.project_name).trim() : ""
      const role = p?.role != null ? String(p.role).trim() : ""
      const time = p?.time != null ? String(p.time).trim() : ""
      const headLine = [projectName, role, time].filter(Boolean).join(" · ")
      
      let text = headLine ? `**${headLine}**\n` : ""

      // 🌟 新结构：source_link
      const sourceLink = p?.source_link != null ? String(p.source_link).trim() : ""
      if (sourceLink) text += `${sourceLink}\n`

      // 🌟 新结构：tech_stack
      const techStack = p?.tech_stack != null ? String(p.tech_stack).trim() : ""
      if (techStack) text += `${techStack}\n`

      // 🌟 新结构：background
      const background = p?.background != null ? String(p.background).trim() : ""
      if (background) text += `${background}\n`

      // 🌟 新结构：implementation (包含 title 和 points 数组)
      if (p?.implementation && typeof p.implementation === "object") {
        const implTitle = p.implementation.title != null ? String(p.implementation.title).trim() : ""
        if (implTitle) text += `${implTitle}\n`
        
        if (Array.isArray(p.implementation.points)) {
          for (const point of p.implementation.points) {
            const pointText = String(point ?? "").trim()
            if (pointText) text += `${pointText}\n`
          }
        }
      }

      // 🌟 新结构：results
      const results = p?.results != null ? String(p.results).trim() : ""
      if (results) text += `${results}\n`

      // 兼容旧结构（如果新字段都不存在，尝试旧的 STAR 结构）
      if (!sourceLink && !techStack && !background && !p?.implementation && !results) {
        const bg = p?.star_s_background != null ? String(p.star_s_background).trim() : ""
        if (bg) text += `${bg}\n`

        const task = p?.star_t_task != null ? String(p.star_t_task).trim() : ""
        if (task) text += `${task}\n`

        if (Array.isArray(p?.star_a_actions)) {
          for (const act of p.star_a_actions) {
            const subtitle = act?.subtitle != null ? String(act.subtitle).trim() : ""
            const description = act?.description != null ? String(act.description).trim() : ""
            if (!subtitle && !description) continue
            
            if (subtitle && description) {
              text += `• **${subtitle}**：${description}\n`
            } else if (subtitle) {
              text += `• **${subtitle}**：\n`
            } else {
              text += `• ${description}\n`
            }
          }
        }

        const oldResults = p?.star_r_results != null ? String(p.star_r_results).trim() : ""
        if (oldResults) text += `${oldResults}\n`
      }

      if (text.trim()) projectBlocks.push(text.trim())
    }
    projectContent = projectBlocks.join("\n\n")
  }

  let workContent = ""
  if (Array.isArray(data.work_experience)) {
    const workBlocks: string[] = []
    for (const w of data.work_experience) {
      const company = w?.company_name != null ? String(w.company_name).trim() : w?.company != null ? String(w.company).trim() : ""
      const title = w?.title != null ? String(w.title).trim() : w?.position != null ? String(w.position).trim() : ""
      const time = w?.time != null ? String(w.time).trim() : ""
      const headLine = [company, title, time].filter(Boolean).join(" · ")
      
      let text = headLine ? `**${headLine}**\n` : ""

      // 🌟 新结构：experience_points 数组
      if (Array.isArray(w?.experience_points)) {
        for (const point of w.experience_points) {
          const pointText = String(point ?? "").trim()
          if (pointText) text += `${pointText}\n`
        }
      } else if (Array.isArray(w?.actions)) {
        // 兼容旧结构：actions 数组
        for (const a of w.actions) {
          const subtitle = a?.subtitle != null ? String(a.subtitle).trim() : ""
          const description = a?.description != null ? String(a.description).trim() : ""
          const result = a?.result != null ? String(a.result).trim() : ""

          if (subtitle || description) {
            if (subtitle && description) {
              text += `• **${subtitle}**：${description}\n`
            } else if (subtitle) {
              text += `• **${subtitle}**：\n`
            } else {
              text += `• ${description}\n`
            }
          }
          if (result) text += `${result}\n`
        }
      }

      if (text.trim()) workBlocks.push(text.trim())
    }
    workContent = workBlocks.join("\n\n")
  }

  let educationContent = ""
  if (Array.isArray(data.education)) {
    educationContent = data.education
      .map((e: any) => {
        const school = e?.school != null ? String(e.school) : ""
        const degree = e?.degree != null ? String(e.degree) : ""
        const time = e?.time != null ? String(e.time) : ""
        return [school, degree, time].filter(Boolean).join(" · ")
      })
      .filter(Boolean)
      .join("\n")
  }

  const sections: ResumeSection[] = [
    { id: "summary", title: "个人总结", content: summaryContent },
    { id: "skills", title: "专业技能", content: skillsContent },
    { id: "project", title: "项目经历", content: projectContent },
    { id: "work", title: "工作经历", content: workContent },
    { id: "education", title: "教育背景", content: educationContent },
  ]

  return { header, sections }
}

async function fetchDefaultResumeData(): Promise<ResumeData> {
  try {
    // 🌟 1. 优先从你的“策略大盘”拉取启用的云端简历
    const strategyRes = await fetch("http://127.0.0.1:8000/api/strategy/config")
    if (strategyRes.ok) {
      const strategyData = await strategyRes.json()
      // 找出当前状态为"启用"的简历
      const activeResume = strategyData.resumes?.find((r: any) => r.status === "启用")
      
      if (activeResume && activeResume.content) {
        const parsed = parseResumeData(activeResume.content)
        if (parsed) {
          console.log("✅ 成功加载云端默认简历")
          return parsed
        }
      }
    }

    // 🌟 2. 如果云端没有找到启用的简历或解析失败，降级读取本地测试文件
    console.warn("⚠️ 未找到启用的云端简历，降级使用本地 default_resume.json")
    const response = await fetch("/default_resume.json")
    if (!response.ok) return DEFAULT_RESUME
    const data = await response.json()
    return transformJsonToResumeData(data)
    
  } catch (e) {
    console.error("加载默认简历失败:", e)
    return DEFAULT_RESUME
  }
}

function parseResumeData(raw: string): ResumeData | null {
  if (!raw) return null;
  const parsed = safeParseJSON(raw);
  if (!parsed) return null;

  // 🌟 如果解析出来是纯字符串（说明读取到的是纯 Markdown 文本）
  if (typeof parsed === 'string') {
    let pureMarkdown = parsed;

    // 🚀 核心拦截 1：强行切断大模型在末尾附加的 `# 待办与补充清单`
    const todoIndex = pureMarkdown.search(/(?:\n|^)#\s*待办与补充清单/i);
    if (todoIndex !== -1) {
      pureMarkdown = pureMarkdown.slice(0, todoIndex);
    }

    // 🚀 核心拦截 2：剔除正文里所有的 `> 💡 Copilot 优化思路：...` 挂载理由
    pureMarkdown = pureMarkdown.replace(/(?:\n|^)>\s*💡\s*Copilot\s*优化思路[^\n]*/gi, '');

    // 🚀 核心拦截 3：兼容处理可能残留的其他旧版说明标题
    const oldAnnotationRegex = /(?:\n|^)(?:---*\s*\n)?(?:#+\s*)?(?:\*\*|__)?(?:改写说明|修改说明|修改理由|简历改写与对标批注)(?:\*\*|__)?(?:：|:)?\s*\n/i;
    const matchIndex = pureMarkdown.search(oldAnnotationRegex);
    if (matchIndex !== -1) {
      pureMarkdown = pureMarkdown.slice(0, matchIndex);
    }

    // 🚀 核心拦截 4：剔除顶部的 "# 简历重构方案" 废话标题
    pureMarkdown = pureMarkdown.replace(/(?:\n|^)#\s*简历重构方案\s*\n/gi, '\n');

    // 🚀 核心拦截 5：剔除正文任何位置（包括末尾）的 JSON 说明块 (避免污染中间的简历画板)
    pureMarkdown = pureMarkdown.replace(/(?:\n|^)\s*\{[\s\S]*?"rewrite_rationale"[\s\S]*?\}\s*(?=\n#|\n##|$)/g, '\n');

    // 🚀 核心拦截 6：剔除底部的重构说明
    pureMarkdown = pureMarkdown.replace(/(?:\n|^)(?:---|___)?\s*\n?\s*\**重构说明\**[：:][\s\S]*$/i, '\n');

    // 🚀 核心拦截 7：修复双重标题 (把大模型写错的 "## # 个人总结" 变成 "# 个人总结")
    pureMarkdown = pureMarkdown.replace(/(?:\n|^)##\s*#\s*/g, '\n# ');

    // 清理剔除后产生的多余空行
    pureMarkdown = pureMarkdown.replace(/\n{3,}/g, '\n\n').trim();

    const lines = pureMarkdown.split('\n');
    // ... (保留后面的遍历逻辑不变)
    const sections: ResumeSection[] = [];
    let currentTitle = "";
    let currentContent: string[] = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      
      // 精准匹配一级标题
      const match = line.match(/^#([^#].*)$/);
      
      if (match) {
        if (currentTitle || currentContent.join('').trim()) {
          sections.push({
            id: `md-section-${sections.length}-${Date.now()}`,
            title: currentTitle || "未命名模块",
            content: currentContent.join('\n').trim()
          });
        }
        currentTitle = match[1].trim();
        currentContent = [];
      } else {
        currentContent.push(line);
      }
    }

    if (currentTitle || currentContent.join('').trim()) {
      sections.push({
        id: `md-section-${sections.length}-${Date.now()}`,
        title: currentTitle || "导入内容",
        content: currentContent.join('\n').trim()
      });
    }

    return {
      ...DEFAULT_RESUME, 
      sections: sections
    };
  }

  return transformJsonToResumeData(parsed);
}

function replaceAllText(value: string, findText: string, replaceText: string): string {
  if (!findText) return value
  return value.split(findText).join(replaceText)
}

function splitTagString(input: any): string[] {
  if (Array.isArray(input)) {
    const filtered = input.filter(Boolean).map(String)
    return Array.from(new Set(filtered))
  }
  if (!input || typeof input !== "string") return []
  const tags = input
    .split(/[\s,，、;；]+|(?=[A-Z])/)
    .map((item) => item.trim())
    .filter(Boolean)
  return Array.from(new Set(tags))
}

function formatDateMaybeTimestamp(value: string): string {
  const ts = Number(value)
  if (!Number.isNaN(ts) && ts > 100000000000) {
    return new Date(Number(ts)).toLocaleDateString("zh-CN")
  }
  return value || "-"
}

function EditableSection({
  section,
  isMatched,
  onSelectText,
  onCommit,
  onDragStart,
  onDropTo,
  onMoveUp,
  onMoveDown,
  findText,
  currentMatchIndex,
  onRegisterMatch,
}: EditableSectionProps) {
  const [localTitle, setLocalTitle] = useState(section.title)
  const [localContent, setLocalContent] = useState(section.content)
  const [isEditing, setIsEditing] = useState(false)

  // 🌟 核心修复：彻底拔掉无限刷新死循环的引擎
  const onCommitRef = useRef(onCommit)
  useEffect(() => {
    onCommitRef.current = onCommit
  }, [onCommit])

  useEffect(() => {
    setLocalTitle(section.title)
  }, [section.id, section.title])

  useEffect(() => {
    setLocalContent(section.content)
  }, [section.id, section.content])

  useEffect(() => {
    const timer = setTimeout(() => {
      if (localTitle !== section.title || localContent !== section.content) {
        onCommitRef.current({ ...section, title: localTitle, content: localContent })
      }
    }, 500)
    return () => clearTimeout(timer)
    // 🌟 严格限制依赖，父组件怎么刷都不受影响
  }, [localTitle, localContent, section.title, section.content, section.id])

  // 🌟 切换岗位时重置编辑状态
  useEffect(() => {
    setIsEditing(false)
  }, [section.id])

  const flushCommit = () => {
    if (localTitle !== section.title || localContent !== section.content) {
      onCommitRef.current({ ...section, title: localTitle, content: localContent })
    }
  }

  const getSectionMinHeightClass = (sectionId: string) => {
    if (sectionId === "summary") return "min-h-[100px]"
    if (sectionId === "skills") return "min-h-[150px]"
    if (sectionId === "project" || sectionId === "work" || sectionId === "experience") {
      return "min-h-[250px]"
    }
    return "min-h-[100px]"
  }

  return (
    <div
      className={`rounded ${isMatched ? "ring-1 ring-amber-300" : ""}`}
      onDragOver={(e) => e.preventDefault()}
      onDrop={() => onDropTo(section.id)}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <Input
          value={localTitle}
          onChange={(e) => setLocalTitle(e.target.value)}
          onBlur={flushCommit}
          className="h-6 text-xs border-none bg-transparent p-0 font-semibold"
        />
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 text-muted-foreground cursor-grab active:cursor-grabbing"
            draggable
            onDragStart={() => onDragStart(section.id)}
            title="拖拽调整顺序"
          >
            <GripVertical className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="sm" className="h-6 px-1.5 text-[10px]" onClick={onMoveUp}>
            <ArrowUp className="h-3 w-3 mr-1" />
            上移
          </Button>
          <Button variant="ghost" size="sm" className="h-6 px-1.5 text-[10px]" onClick={onMoveDown}>
            <ArrowDown className="h-3 w-3 mr-1" />
            下移
          </Button>
        </div>
      </div>
      {findText ? (
        <div
          className={`w-full ${getSectionMinHeightClass(
            section.id,
          )} overflow-y-auto text-[11px] leading-tight whitespace-pre-wrap break-words border border-gray-300 rounded-sm p-2 ${
            isMatched ? "border-amber-300 bg-amber-50/50" : ""
          }`}
        >
          <HighlightText
            text={localContent}
            searchKeyword={findText}
            currentMatchIndex={currentMatchIndex}
            onRegisterMatch={onRegisterMatch}
          />
        </div>
      ) : isEditing ? (
        <Textarea
          className={`w-full min-h-[500px] !resize-y overflow-y-auto text-sm leading-relaxed text-gray-600 dark:text-muted-foreground whitespace-pre-wrap break-words user-select-text cursor-text border border-gray-300 rounded-sm p-2 outline-none ${
            isMatched ? "border-amber-300 bg-amber-50/50" : "hover:border-input"
          }`}
          value={localContent}
          onChange={(e) => setLocalContent(e.target.value)}
          onBlur={() => { flushCommit(); setIsEditing(false) }}
          onSelect={(e) => {
            const target = e.currentTarget
            const text = target.value.slice(target.selectionStart ?? 0, target.selectionEnd ?? 0).trim()
            onSelectText(text, section.id)
          }}
          autoFocus
        />
      ) : (
        <div
          className={`w-full ${getSectionMinHeightClass(section.id)} cursor-text p-2 rounded-sm border transition-colors ${
            isMatched
              ? "border-amber-300 bg-amber-50/50"
              : "border-transparent hover:border-gray-200 hover:bg-gray-50/30"
          }`}
          onClick={() => setIsEditing(true)}
          title="点击编辑"
        >
          <MdPreview text={localContent} />
        </div>
      )}
    </div>
  )
}

// ── 10维度评估大盘 ──────────────────────────────────────
const GRADE_STYLE: Record<string, { bg: string; ring: string; label: string; desc: string }> = {
  A: { bg: "from-yellow-400 to-orange-500", ring: "ring-yellow-400", label: "A", desc: "顶级匹配" },
  B: { bg: "from-emerald-400 to-teal-500", ring: "ring-emerald-400", label: "B", desc: "良好匹配" },
  C: { bg: "from-blue-400 to-indigo-500", ring: "ring-blue-400", label: "C", desc: "一般匹配" },
  D: { bg: "from-orange-400 to-red-400", ring: "ring-orange-400", label: "D", desc: "较差匹配" },
  F: { bg: "from-gray-300 to-gray-400", ring: "ring-gray-300", label: "F", desc: "不匹配" },
}

const DIM_CONFIG = [
  { key: "roleMatch" as const,     label: "角色匹配", tag: "核心", dot: "bg-purple-500" },
  { key: "skillsAlign" as const,   label: "技能重合", tag: "核心", dot: "bg-purple-500" },
  { key: "seniority" as const,     label: "职级资历", tag: "高权", dot: "bg-amber-500" },
  { key: "compensation" as const,  label: "薪资契合", tag: "高权", dot: "bg-amber-500" },
  { key: "interviewProb" as const, label: "面试概率", tag: "高权", dot: "bg-amber-500" },
  { key: "workMode" as const,      label: "工作模式", tag: "中权", dot: "bg-blue-500" },
  { key: "companyStage" as const,  label: "公司阶段", tag: "中权", dot: "bg-blue-500" },
  { key: "marketFit" as const,     label: "赛道前景", tag: "中权", dot: "bg-blue-500" },
  { key: "growth" as const,        label: "成长空间", tag: "中权", dot: "bg-blue-500" },
  { key: "timeline" as const,      label: "招聘周期", tag: "低权", dot: "bg-gray-400" },
]

function AiGradeDashboard({ job }: { job: JobData }) {
  const grade = job.grade ?? ""
  const gs = GRADE_STYLE[grade]
  const rawTotal = DIM_CONFIG.reduce((s, d) => s + (Number(job[d.key]) || 0), 0)

  return (
    <div className="space-y-2.5">
      {/* Grade Hero */}
      <div className={`flex items-center gap-3 p-3 rounded-xl bg-gradient-to-r ${gs ? gs.bg : "from-gray-100 to-gray-200"}`}>
        <div className={`h-12 w-12 rounded-xl bg-white/20 flex items-center justify-center font-black text-2xl text-white shadow-inner ring-2 ${gs ? gs.ring : "ring-gray-300"}`}>
          {gs ? gs.label : "?"}
        </div>
        <div>
          <p className="text-white font-bold text-sm">{gs ? gs.desc : "暂未评估"}</p>
          <p className="text-white/80 text-xs">{rawTotal > 0 ? `综合 ${rawTotal}/50 分` : "等待 AI 评估"}</p>
        </div>
      </div>

      {/* 10-dim grid */}
      {rawTotal > 0 && (
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
          {DIM_CONFIG.map((d) => {
            const score = Number(job[d.key]) || 0
            return (
              <div key={d.key} className="flex flex-col gap-0.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground">{d.label}</span>
                  <span className={`text-[9px] px-1 rounded-full font-medium ${
                    d.tag === "核心" ? "bg-purple-100 text-purple-700" :
                    d.tag === "高权" ? "bg-amber-100 text-amber-700" :
                    d.tag === "中权" ? "bg-blue-100 text-blue-700" :
                    "bg-gray-100 text-gray-500"
                  }`}>{d.tag}</span>
                </div>
                <div className="flex gap-0.5">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <div
                      key={i}
                      className={`h-1.5 flex-1 rounded-full ${i <= score ? d.dot : "bg-gray-200"}`}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
// ─────────────────────────────────────────────────────────

export function JobDetailWorkspace({
  job,
  onUpdateJob,
  onBack,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  dynamicStatuses,
  onRefreshJobs,
}: JobDetailWorkspaceProps) {
  const [status, setStatus] = useState(job?.followStatus || "")
  const [resumeData, setResumeData] = useState<ResumeData>(DEFAULT_RESUME)
  const [selectedText, setSelectedText] = useState("")
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null)
  const [history, setHistory] = useState<ResumeData[]>([])
  const [exportingType, setExportingType] = useState<"word" | "pdf" | "image" | null>(null)
  const [qaReport, setQaReport] = useState<any>(null)
  const [tplModalOpen, setTplModalOpen] = useState(false)
  const [exportTemplates, setExportTemplates] = useState<{name: string; size: number; is_default: boolean}[]>([])
  const [selectedTplName, setSelectedTplName] = useState("")
  const [pendingExportType, setPendingExportType] = useState<"word" | "pdf" | "image" | null>(null)

  // 容错处理：确保当前状态始终在选项中
  const availableStatuses = useMemo(() => {
    const currentStatus = job?.followStatus?.trim()
    if (currentStatus && !dynamicStatuses.includes(currentStatus)) {
      return [...dynamicStatuses, currentStatus].sort()
    }
    return dynamicStatuses
  }, [dynamicStatuses, job?.followStatus])

  useEffect(() => {
    if (job) {
      setStatus(job.followStatus || "")
      
      // 🌟 初始化 QA 报告：优先从飞书的 secondQaReport 字段读取
      if (job.secondQaReport && job.secondQaReport.trim()) {
        try {
          const parsedReport = JSON.parse(job.secondQaReport)
          setQaReport(parsedReport)
        } catch (e) {
          console.error("解析 QA 报告失败:", e)
          setQaReport(null)
        }
      } else {
        setQaReport(null)
      }
    }
  }, [job?.followStatus, job?.id, job?.secondQaReport])

  // 🌟 LocalStorage 姓名记忆功能：客户端挂载后安全读取
  useEffect(() => {
    if (typeof window === 'undefined') return; // SSR 安全检查
    
    const savedName = localStorage.getItem('candidateName');
    if (savedName && savedName.trim()) {
      setResumeData((prev) => ({
        ...prev,
        header: { ...prev.header, name: savedName.trim() }
      }));
    }
  }, []); // 仅在组件挂载时执行一次

  useEffect(() => {
    if (!job) return;
    
    // 🌟 优先使用人工精修版简历，如果为空则兜底使用 AI 改写 JSON
    if (job.manualRefinedResume) {
      const fromManual = parseResumeData(job.manualRefinedResume)
      if (fromManual) {
        setResumeData(fromManual)
        setHistory([])
        return
      }
    }
    
    const fromAi = parseResumeData(job.aiRewriteJson)
    if (fromAi) {
      setResumeData(fromAi)
      setHistory([])
      return
    }
    
    let cancelled = false
    fetchDefaultResumeData().then((data) => {
      if (!cancelled) {
        setResumeData(data)
        setHistory([])
      }
    })
    return () => {
      cancelled = true
    }
  }, [job?.id, job?.aiRewriteJson, job?.manualRefinedResume])

  const handleResumeChange = useCallback((next: ResumeData) => {
    setResumeData((prev) => {
      setHistory((h) => [...h.slice(-49), prev])
      return next
    })
  }, [])

  const handleUndo = useCallback(() => {
    setHistory((h) => {
      if (h.length === 0) return h
      const prev = h[h.length - 1]
      setResumeData(prev)
      return h.slice(0, -1)
    })
  }, [])

  const handlePolishSelected = useCallback(
    async (instruction: string) => {
      if (!selectedText.trim() || !selectedSectionId) {
        alert("请先在简历正文中选中一段文字")
        return
      }
      try {
        const response = await fetch("http://127.0.0.1:8000/ai_polish", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ selected_text: selectedText, instruction }),
        })
        const data = await response.json()
        const polished = typeof data?.polished_text === "string" ? data.polished_text : selectedText
        if (data?.error) {
          console.warn(data.error)
        }
        setResumeData((prev) => ({
          ...prev,
          sections: prev.sections.map((s) =>
            s.id === selectedSectionId
              ? { ...s, content: s.content.split(selectedText).join(polished) }
              : s,
          ),
        }))
        setSelectedText(polished)
      } catch {
        alert("润色请求失败，请确认后端已启动")
      }
    },
    [selectedText, selectedSectionId],
  )

  const handleExportWithTemplate = async (type: "word" | "pdf" | "image") => {
    setPendingExportType(type)
    try {
      const res = await fetch("http://127.0.0.1:8000/api/templates")
      const data = await res.json()
      if (data.status === "success" && data.templates.length > 0) {
        setExportTemplates(data.templates)
        setSelectedTplName(data.default || data.templates[0]?.name || "")
        setTplModalOpen(true)
        return
      }
    } catch {
      // fall through to default export
    }
    handleExport(type)
  }

  const handleExport = async (type: "word" | "pdf" | "image", templateName?: string) => {
    if (!job?.id) {
      alert("错误：无法获取当前岗位 ID")
      return
    }
    setExportingType(type)
    try {
      const response = await fetch("http://127.0.0.1:8000/export_resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: job.id,
          export_type: type,
          resume_data: resumeData,
          template_name: templateName ?? undefined,
        }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        const d = data.detail
        const detailStr = Array.isArray(d)
          ? d.map((x: { msg?: string }) => x?.msg ?? String(x)).join("；")
          : typeof d === "string"
            ? d
            : ""
        alert("❌ " + (detailStr || data.msg || response.statusText || "请求失败"))
        return
      }
      if (data.status === "success") {
        alert("✅ " + (data.msg || "导出成功"))
      } else {
        alert("❌ 失败：" + (data.msg || "未知错误"))
      }
    } catch {
      alert("❌ 网络错误，请检查后端是否运行")
    } finally {
      setExportingType(null)
    }
  }

  // 🌟 防止白屏崩溃
  if (!job) {
     return <div className="h-full flex items-center justify-center text-sm text-muted-foreground">正在加载岗位数据...</div>
  }

  return (
    <div className="h-full flex flex-col bg-muted/30">
      <header className="px-4 py-2.5 border-b border-border bg-card flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onBack} className="h-8 gap-1.5">
            <ArrowLeft className="h-4 w-4" />
            返回列表
          </Button>
          <div className="h-5 w-px bg-border" />
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={onPrevious} 
            disabled={!hasPrevious}
            className="h-8 gap-1 px-2"
            title="上一个岗位"
          >
            <ChevronLeft className="h-4 w-4" />
            上一个
          </Button>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={onNext} 
            disabled={!hasNext}
            className="h-8 gap-1 px-2"
            title="下一个岗位"
          >
            下一个
            <ChevronRight className="h-4 w-4" />
          </Button>
          <div className="h-5 w-px bg-border" />
          <Select 
            value={status} 
            onValueChange={(newStatus) => {
              // 1. 立即更新本地 UI 状态
              setStatus(newStatus);
              if (newStatus === (job?.followStatus || "")) return;

              // 2. ⚡️ 乐观更新核心：瞬间操作父组件状态，不要等待 API
              if (newStatus === "不合适") {
                // 触发父组件的移除并跳转下一个逻辑
                onUpdateJob(null, 'remove'); 
              } else {
                // 普通状态更新
                onUpdateJob({ ...job, followStatus: newStatus });
              }

              // 3. 🚀 后台静默发送请求，坚决不能加 await 阻塞 UI
              fetch("http://127.0.0.1:8000/api/update_job_status", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ 
                  job_id: job?.id || "", 
                  status: newStatus,
                  platform: job?.platform || "BOSS直聘" 
                }),
              }).then(async (response) => {
                const data = await response.json();
                if (!response.ok || data.status !== "success") {
                  console.error("❌ 状态同步失败:", data.message || data.detail);
                  // 乐观更新原则：为了不打断体验，后台报错仅打印日志，不弹窗阻断用户
                }
              }).catch(error => {
                console.error("网络错误:", error);
              });

              // 4. 🚨 彻底移除此处原本的 if (onRefreshJobs) await onRefreshJobs(); 全局刷新逻辑
            }}
          >
            <SelectTrigger className="w-28 h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {availableStatuses.map((statusOption) => (
                <SelectItem key={statusOption} value={statusOption}>
                  {statusOption}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className="font-medium text-foreground text-sm">{job.jobTitle || "-"}</span>
          <span className="text-muted-foreground text-sm">·</span>
          <span className="text-muted-foreground text-sm">{job.companyName || "-"}</span>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={() => handleExportWithTemplate("word")}
            disabled={exportingType !== null}
          >
            {exportingType === "word" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            {exportingType === "word" ? "生成中..." : "保存 Word"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={() => handleExportWithTemplate("image")}
            disabled={exportingType !== null}
          >
            {exportingType === "image" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Image className="h-3.5 w-3.5" />
            )}
            {exportingType === "image" ? "生成中..." : "生成图片"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={() => handleExportWithTemplate("pdf")}
            disabled={exportingType !== null}
          >
            {exportingType === "pdf" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <FileText className="h-3.5 w-3.5" />
            )}
            {exportingType === "pdf" ? "生成中..." : "导出 PDF"}
          </Button>
        </div>
      </header>

      <div className="flex-1 overflow-hidden p-2">
        <ResizablePanelGroup direction="horizontal" className="h-full rounded-lg border border-border">
          <ResizablePanel defaultSize={25} minSize={20} maxSize={35}>
            <JobArchiveColumn job={job} onBack={onBack} />
          </ResizablePanel>

          <ResizableHandle withHandle />

          <ResizablePanel defaultSize={50} minSize={35}>
            <ResumeCanvasColumn
              resumeData={resumeData}
              onChange={handleResumeChange}
              selectedText={selectedText}
              selectedSectionId={selectedSectionId}
              onClearSelection={() => {
                setSelectedText("")
                setSelectedSectionId(null)
              }}
              onTextSelect={(text, sectionId) => {
                setSelectedText(text)
                setSelectedSectionId(sectionId)
              }}
              onUndo={handleUndo}
              canUndo={history.length > 0}
              job={job}
              onQAComplete={(report) => setQaReport(report)}
              onUpdateJob={onUpdateJob}
            />
          </ResizablePanel>

          <ResizableHandle withHandle />

          <ResizablePanel defaultSize={25} minSize={20} maxSize={35}>
            <AICopilotColumn
              job={job}
              onUpdateJob={onUpdateJob}
              selectedText={selectedText}
              onPolish={handlePolishSelected}
              qaReport={qaReport}
            />
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>

      {/* 🌟 模板选择弹窗 */}
      {tplModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-[480px] bg-white rounded-2xl shadow-2xl p-6 flex flex-col gap-4 max-h-[80vh]">
            <div className="flex justify-between items-center shrink-0">
              <h3 className="text-base font-bold text-gray-800">🖨️ 选择导出模板</h3>
              <button onClick={() => setTplModalOpen(false)} className="text-gray-400 hover:text-gray-600 p-1">
                <X size={20} />
              </button>
            </div>

            {exportTemplates.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">暂无上传模板，将使用系统内置默认模板</p>
            ) : (
              <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                {exportTemplates.map((tpl) => (
                  <label
                    key={tpl.name}
                    className={`flex items-center gap-3 p-3.5 rounded-xl border cursor-pointer transition-colors ${
                      selectedTplName === tpl.name
                        ? "border-blue-500 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                    }`}
                  >
                    <input
                      type="radio"
                      name="export-template"
                      checked={selectedTplName === tpl.name}
                      onChange={() => setSelectedTplName(tpl.name)}
                      className="accent-blue-600 w-4 h-4 shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm text-gray-800 truncate">{tpl.name}</div>
                      <div className="text-xs text-gray-400 mt-0.5">{(tpl.size / 1024).toFixed(1)} KB</div>
                    </div>
                    {tpl.is_default && (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium whitespace-nowrap">默认</span>
                    )}
                  </label>
                ))}
              </div>
            )}

            <div className="flex justify-end gap-3 pt-2 border-t border-gray-100 shrink-0">
              <Button variant="ghost" onClick={() => setTplModalOpen(false)}>取消</Button>
              <Button
                onClick={() => {
                  setTplModalOpen(false)
                  if (pendingExportType) {
                    handleExport(pendingExportType, selectedTplName || undefined)
                    setPendingExportType(null)
                  }
                }}
                className="gap-2"
              >
                确认导出
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 🌟 全局悬浮 AI Copilot Widget */}
      <FloatingCopilotWidget job={job} selectedText={selectedText} />
    </div>
  )
}

function JobArchiveColumn({ job, onBack }: { job: JobData | null; onBack: () => void }) {
  if (!job) return null;

  return (
    <div className="h-full bg-card flex flex-col">
      <div className="px-3 py-2 border-b border-border shrink-0">
        <h3 className="font-medium text-xs text-foreground flex items-center gap-1.5">
          <FileText className="h-3.5 w-3.5" />
          岗位存档
        </h3>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        <div className="space-y-3">
          <div className="space-y-2 text-xs">
            <MetaItem label="岗位名称" value={job.jobTitle || "-"} />
            <MetaItem label="公司名称" value={job.companyName || "-"} />
            <MetaItem label="城市" value={job.location || "-"} />
            <MetaItem
              label="薪资"
              value={job.salary || "-"}
              valueClassName="text-orange-500 font-semibold"
            />
            <MetaItem label="AI总分(旧)" value={`${job.aiScore ?? 0}分`} valueClassName="text-muted-foreground" />
            <MetaItem label="初步打分" value={`${job.preliminaryScore ?? 0}分`} />
            <MetaItem 
            label="加分词" 
            value={job.bonusWords || "-"} 
            valueClassName="text-green-600 font-medium" 
            />
            <MetaItem 
            label="减分词" 
            value={job.deductionWords || "-"} 
            valueClassName="text-red-500 font-medium" 
/>
            <MetaItem label="公司规模" value={job.companyScale || "-"} />
            <MetaItem label="所属行业" value={job.industry || "-"} />
            <MetaItem label="学历要求" value={job.education || "-"} />
            <MetaItem label="经验要求" value={job.experience || "-"} />
            <MetaItem label="HR活跃度" value={job.hrActivity || "-"} />
            <MetaItem 
              label="📅 发布日期" 
              value={job.publishDate || "-"} 
              valueClassName="text-blue-600 font-medium"
            />
            <MetaItem 
              label="👤 角色" 
              value={job.role || "-"} 
              valueClassName={job.role === "猎头" ? "text-orange-600 font-semibold" : "text-green-600 font-medium"}
            />
            <MetaItem label="投递日期" value={formatDateMaybeTimestamp(job.applyDate || "-")} />
            <MetaItem label="抓取时间" value={formatDateMaybeTimestamp(job.captureTime || "-")} />
            <MetaItem label="工作地址" value={job.workAddress || "-"} />
          </div>

          {splitTagString(job.hrSkills).length > 0 && (
            <div className="pt-2 border-t border-border">
              <h4 className="text-xs font-medium text-muted-foreground mb-1.5">HR技能标签</h4>
              <div className="flex flex-wrap gap-1.5">
                {splitTagString(job.hrSkills).map((skill, index) => (
                  <Badge key={`${skill}-${index}`} className="text-xs bg-blue-100 text-blue-800 hover:bg-blue-100">
                    {skill}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {splitTagString(job.benefits).length > 0 && (
            <div className="pt-2 border-t border-border">
              <h4 className="text-xs font-medium text-muted-foreground mb-1.5">福利标签</h4>
              <div className="flex flex-wrap gap-1.5">
                {splitTagString(job.benefits).map((benefit, index) => (
                  <Badge key={`${benefit}-${index}`} className="text-xs bg-green-100 text-green-800 hover:bg-green-100">
                    {benefit}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {job.directLink && job.directLink !== "#" && (
            <Button variant="outline" size="sm" className="w-full gap-1.5 h-7 text-xs" asChild>
              <a href={job.directLink} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-3 w-3" />
                岗位详情链接
              </a>
            </Button>
          )}

          <div className="pt-2 border-t border-border">
            <div className="flex flex-wrap gap-1.5">
              <Badge className={`text-xs ${getStatusBadgeColor(job.followStatus || "新线索")}`}>
                {job.followStatus || "新线索"}
              </Badge>
            </div>
          </div>

          <div className="pt-2 border-t border-border">
            <h4 className="text-xs font-medium text-muted-foreground mb-1.5">
              岗位详情
            </h4>
            <div className="text-xs text-foreground whitespace-pre-line leading-relaxed">
              {job.jobDescription || "暂无岗位详情"}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function MetaItem({
  label,
  value,
  valueClassName = "",
}: {
  label: string
  value: string | number
  valueClassName?: string
}) {
  return (
    <div className="flex items-start justify-between gap-2">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className={`text-foreground text-right ${valueClassName}`}>{value}</span>
    </div>
  )
}

function ResumeCanvasColumn({
  resumeData,
  onChange,
  selectedText,
  selectedSectionId,
  onClearSelection,
  onTextSelect,
  onUndo,
  canUndo,
  job,
  onQAComplete,
  onUpdateJob,
}: {
  resumeData: ResumeData
  onChange: (value: ResumeData) => void
  selectedText: string
  selectedSectionId: string | null
  onClearSelection: () => void
  onTextSelect: (value: string, sectionId: string | null) => void
  onUndo: () => void
  canUndo: boolean
  job: JobData | null
  onQAComplete?: (qaReport: any) => void
  onUpdateJob: (job: JobData | null, action?: 'remove') => void
}) {
  const [hoveredBlock, setHoveredBlock] = useState<string | null>(null)
  const [findText, setFindText] = useState("")
  const [replaceText, setReplaceText] = useState("")
  const [matchedSectionIds, setMatchedSectionIds] = useState<string[]>([])
  const [draggingSectionId, setDraggingSectionId] = useState<string | null>(null)
  const [isQAEvaluating, setIsQAEvaluating] = useState(false)
  const [qaStatus, setQaStatus] = useState("")
  const [isSavingResume, setIsSavingResume] = useState(false)
  const [totalMatches, setTotalMatches] = useState(0)
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0)
  const matchIdsRef = useRef<string[]>([])

  const moveSection = (index: number, direction: -1 | 1) => {
    const next = index + direction
    if (next < 0 || next >= resumeData.sections.length) return
    const arr = [...resumeData.sections]
    const [current] = arr.splice(index, 1)
    arr.splice(next, 0, current)
    onChange({ ...resumeData, sections: arr })
  }

  const handleBold = () => {
    const trimmed = selectedText.trim()
    if (!trimmed || !selectedSectionId) {
      window.alert("请先选中文本")
      return
    }
    const section = resumeData.sections.find((s) => s.id === selectedSectionId)
    if (!section || !section.content.includes(trimmed)) {
      window.alert("请先选中文本")
      return
    }
    const wrapped = `**${trimmed}**`
    const newContent = section.content.replace(trimmed, wrapped)
    const nextSections = resumeData.sections.map((s) =>
      s.id === selectedSectionId ? { ...s, content: newContent } : s,
    )
    onChange({ ...resumeData, sections: nextSections })
    onClearSelection()
  }

  const handleDropTo = (targetSectionId: string) => {
    if (!draggingSectionId || draggingSectionId === targetSectionId) return
    const from = resumeData.sections.findIndex((s) => s.id === draggingSectionId)
    const to = resumeData.sections.findIndex((s) => s.id === targetSectionId)
    if (from < 0 || to < 0) return
    const next = [...resumeData.sections]
    const [moved] = next.splice(from, 1)
    next.splice(to, 0, moved)
    onChange({ ...resumeData, sections: next })
    setDraggingSectionId(null)
  }

  const handleSectionCommit = useCallback((nextSection: ResumeSection) => {
    onChange({
      ...resumeData,
      sections: resumeData.sections.map((s) => (s.id === nextSection.id ? nextSection : s)),
    })
  }, [resumeData, onChange])

  // 🌟 添加新的自定义模块
  const handleAddSection = useCallback(() => {
    const newSection: ResumeSection = {
      id: `section-${Date.now()}`,
      title: "自定义模块",
      content: "",
    }
    onChange({
      ...resumeData,
      sections: [...resumeData.sections, newSection],
    })
    
    // 平滑滚动到底部
    setTimeout(() => {
      const container = document.querySelector('[data-resume-canvas]')
      if (container) {
        container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
      }
    }, 100)
  }, [resumeData, onChange])

  // 🌟 注册匹配项并返回全局索引
  const registerMatch = useCallback((id: string) => {
    const currentIds = matchIdsRef.current
    const existingIndex = currentIds.indexOf(id)
    if (existingIndex !== -1) {
      return existingIndex
    }
    const newIndex = currentIds.length
    matchIdsRef.current = [...currentIds, id]
    return newIndex
  }, [])

  // 🌟 滚动到指定匹配项并居中
  const scrollToMatch = useCallback((index: number) => {
    if (matchIdsRef.current.length === 0) return
    const matchId = matchIdsRef.current[index]
    if (!matchId) return
    
    const element = document.getElementById(matchId)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [])

  // 🌟 查找功能
  const handleFind = useCallback(() => {
    if (!findText.trim()) {
      matchIdsRef.current = []
      setTotalMatches(0)
      setCurrentMatchIndex(0)
      setMatchedSectionIds([])
      return
    }
    
    // 重置匹配记录
    matchIdsRef.current = []
    
    // 强制重新渲染以收集匹配项
    setCurrentMatchIndex(0)
    
    // 等待下一个渲染周期后滚动
    setTimeout(() => {
      const count = matchIdsRef.current.length
      setTotalMatches(count)
      if (count > 0) {
        scrollToMatch(0)
      }
    }, 100)
    
    // 保留原有的 section 匹配逻辑（用于背景高亮）
    const matched = resumeData.sections
      .filter((s) => s.title.toLowerCase().includes(findText.toLowerCase()) || 
                     s.content.toLowerCase().includes(findText.toLowerCase()))
      .map((s) => s.id)
    setMatchedSectionIds(matched)
  }, [findText, resumeData.sections, scrollToMatch])

  // 🌟 上一个匹配项
  const handlePreviousMatch = useCallback(() => {
    if (totalMatches === 0) return
    const newIndex = currentMatchIndex > 0 ? currentMatchIndex - 1 : totalMatches - 1
    setCurrentMatchIndex(newIndex)
    scrollToMatch(newIndex)
  }, [totalMatches, currentMatchIndex, scrollToMatch])

  // 🌟 下一个匹配项
  const handleNextMatch = useCallback(() => {
    if (totalMatches === 0) return
    const newIndex = currentMatchIndex < totalMatches - 1 ? currentMatchIndex + 1 : 0
    setCurrentMatchIndex(newIndex)
    scrollToMatch(newIndex)
  }, [totalMatches, currentMatchIndex, scrollToMatch])

  // 🌟 监听查找文本变化，自动清理高亮
  useEffect(() => {
    if (!findText.trim()) {
      matchIdsRef.current = []
      setTotalMatches(0)
      setCurrentMatchIndex(0)
      setMatchedSectionIds([])
    }
  }, [findText])

  const handleReplace = (replaceAll: boolean) => {
    if (!findText) return
    const matched = resumeData.sections
      .filter((s) => s.title.includes(findText) || s.content.includes(findText))
      .map((s) => s.id)
    setMatchedSectionIds(matched)
    if (!replaceText || matched.length === 0) return

    const firstMatchId = matched[0]
    const nextSections = resumeData.sections.map((section) => {
      if (!replaceAll && section.id !== firstMatchId) return section
      return {
        ...section,
        title: replaceAllText(section.title, findText, replaceText),
        content: replaceAllText(section.content, findText, replaceText),
      }
    })
    const nextHeader = {
      name: replaceAllText(resumeData.header.name, findText, replaceText),
      contact: replaceAllText(resumeData.header.contact, findText, replaceText),
      intention: replaceAllText(resumeData.header.intention, findText, replaceText),
    }
    onChange({ header: nextHeader, sections: nextSections })
  }

  const handleSaveResume = async () => {
    if (!job?.id) {
      alert("❌ 缺少岗位信息，无法保存简历")
      return
    }

    setIsSavingResume(true)

    try {
      // 🌟 将 resumeData 各模块拼接为 Markdown 文本（格式：# 标题\n\n内容）
      const mdParts: string[] = []
      for (const section of resumeData.sections) {
        if (!section.title.trim() && !section.content.trim()) continue
        mdParts.push(`# ${section.title}`)
        mdParts.push("")
        if (section.content.trim()) mdParts.push(section.content)
        mdParts.push("")
      }
      const resumeMarkdown = mdParts.join("\n").trim()

      const response = await fetch("http://127.0.0.1:8000/api/save_manual_resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: job.id,
          resume_text: resumeMarkdown,
          platform: job.platform || "BOSS直聘"
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        alert("❌ 保存失败：" + (data.detail || "未知错误"))
        return
      }

      if (data.status === "success") {
        // 🌟 保存成功后，更新全局 job 状态，确保 manualRefinedResume 字段同步
        if (onUpdateJob && job) {
          onUpdateJob({
            ...job,
            manualRefinedResume: resumeMarkdown
          })
        }
        alert("✅ 简历已保存到飞书")
      } else {
        alert("❌ 保存失败")
      }
    } catch (error) {
      // 🌟 改进错误提示：显示真实错误信息而非通用提示
      const errorMsg = error instanceof Error ? error.message : String(error)
      alert(`❌ 保存失败：${errorMsg}`)
      console.error("保存简历错误（详细信息）:", error)
    } finally {
      setIsSavingResume(false)
    }
  }

  const handleQAEvaluate = async () => {
    if (!job?.id || !job?.jobDescription) {
      alert("❌ 缺少岗位信息，无法进行 QA 评估")
      return
    }

    setIsQAEvaluating(true)
    setQaStatus("正在进行质检评估...")

    try {
      // 将 resumeData 转换为纯文本
      const resumeText = `${resumeData.header.name}\n${resumeData.header.contact}\n${resumeData.header.intention}\n\n${resumeData.sections.map(s => `${s.title}\n${s.content}`).join("\n\n")}`

      setQaStatus("正在提取人工待办清单...")

      const response = await fetch("http://127.0.0.1:8000/api/qa_evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: job.id,
          job_description: job.jobDescription,
          resume_text: resumeText,
          platform: job.platform || "BOSS直聘"
        }),
      })

      const data = await response.json()

      // 🌟 严格检查：任何非 200 状态码都视为失败
      if (!response.ok) {
        const errorMsg = data.detail || data.message || "未知错误"
        alert(`❌ QA 评估失败：${errorMsg}`)
        setQaStatus("")
        return
      }

      // 🌟 检查返回的 status 字段
      if (data.status === "success" && data.qa_report) {
        setQaStatus("✅ QA 评估完成！")
        onQAComplete?.(data.qa_report)
        
        // 🌟 QA 评估成功后，更新全局 job 状态，确保 secondQaReport 字段同步
        if (onUpdateJob && job) {
          const qaReportJson = typeof data.qa_report === 'string' 
            ? data.qa_report 
            : JSON.stringify(data.qa_report, null, 2)
          onUpdateJob({
            ...job,
            secondQaReport: qaReportJson
          })
        }
        
        setTimeout(() => setQaStatus(""), 3000)
      } else {
        // status 不是 success 或没有 qa_report
        alert("❌ QA 评估失败：后端返回异常数据")
        setQaStatus("")
      }
    } catch (error) {
      // 🌟 改进错误提示：显示真实错误信息而非通用提示
      const errorMsg = error instanceof Error ? error.message : String(error)
      alert(`❌ QA 评估失败：${errorMsg}`)
      console.error("QA 评估错误（详细信息）:", error)
      setQaStatus("")
    } finally {
      setIsQAEvaluating(false)
    }
  }

  return (
    <div className="h-full bg-background flex flex-col">
      <div className="px-3 py-2 border-b border-border bg-card flex flex-col gap-2 shrink-0">
        {/* 第一行：文档编辑工具 */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs px-2 font-bold gap-1"
            onClick={handleBold}
          >
            <Bold className="h-3.5 w-3.5" />
            B 加粗
          </Button>
          <div className="w-px h-5 bg-border" />
          <Search className="h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="查找..."
            value={findText}
            onChange={(e) => setFindText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleFind()
              }
            }}
            className="h-7 text-xs w-28"
          />
          <Button variant="outline" size="sm" className="h-7 text-xs px-2" onClick={handleFind}>
            查找
          </Button>
          {totalMatches > 0 && (
            <>
              <span className="text-xs text-muted-foreground">
                {currentMatchIndex + 1}/{totalMatches}
              </span>
              <Button 
                variant="outline" 
                size="sm" 
                className="h-7 w-7 p-0" 
                onClick={handlePreviousMatch}
                title="上一个"
              >
                <ArrowUp className="h-3.5 w-3.5" />
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                className="h-7 w-7 p-0" 
                onClick={handleNextMatch}
                title="下一个"
              >
                <ArrowDown className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
          <div className="w-px h-5 bg-border" />
          <Replace className="h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="替换为..."
            value={replaceText}
            onChange={(e) => setReplaceText(e.target.value)}
            className="h-7 text-xs w-28"
          />
          <Button variant="outline" size="sm" className="h-7 text-xs px-2" onClick={() => handleReplace(false)}>
            替换
          </Button>
          <Button variant="outline" size="sm" className="h-7 text-xs px-2" onClick={() => handleReplace(true)}>
            全部替换
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs px-2"
            onClick={onUndo}
            disabled={!canUndo}
            title="撤销"
          >
            撤销
          </Button>
        </div>

        {/* 第二行：业务操作按钮 */}
        <div className="flex items-center gap-2 justify-end">
          <Button
            variant="default"
            size="sm"
            className="h-7 text-xs px-3 bg-blue-600 hover:bg-blue-700 gap-1.5"
            onClick={handleSaveResume}
            disabled={isSavingResume}
          >
            {isSavingResume ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                保存中...
              </>
            ) : (
              <>
                <Save className="h-3.5 w-3.5" />
                保存简历
              </>
            )}
          </Button>
          <Button
            variant="default"
            size="sm"
            className="h-7 text-xs px-3 bg-purple-600 hover:bg-purple-700 gap-1.5"
            onClick={handleQAEvaluate}
            disabled={isQAEvaluating}
          >
            {isQAEvaluating ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {qaStatus || "评估中..."}
              </>
            ) : (
              <>
                <Sparkles className="h-3.5 w-3.5" />
                再次AI评估简历
              </>
            )}
          </Button>
        </div>
      </div>

      {/* 🌟 彻底移除灰色底板，换成纯净无边界的沉浸式白底 */}
      <div className="flex-1 overflow-y-auto bg-background flex flex-col items-center py-8" data-resume-canvas>
        <div className="w-full max-w-[794px] min-h-[1123px] h-auto pb-16 bg-background shadow-sm p-8 rounded-xl">
          <div className="space-y-3 text-[11px] leading-tight">
            <EditableBlock
              id="header"
              hoveredBlock={hoveredBlock}
              setHoveredBlock={setHoveredBlock}
            >
              <div className="text-center border-b border-border pb-3">
                <div
                  className="text-sm font-bold text-foreground outline-none"
                  contentEditable
                  suppressContentEditableWarning
                  onBlur={(e) => {
                    const newName = e.currentTarget.innerText.trim();
                    onChange({
                      ...resumeData,
                      header: { ...resumeData.header, name: newName },
                    });
                    // 🌟 LocalStorage 姓名记忆：实时保存到本地存储
                    if (typeof window !== 'undefined' && newName) {
                      localStorage.setItem('candidateName', newName);
                    }
                  }}
                >
                  {resumeData.header.name}
                </div>
                <div
                  className="mt-0.5 text-muted-foreground text-xs outline-none"
                  contentEditable
                  suppressContentEditableWarning
                  onBlur={(e) =>
                    onChange({
                      ...resumeData,
                      header: { ...resumeData.header, contact: e.currentTarget.innerText.trim() },
                    })
                  }
                >
                  {resumeData.header.contact}
                </div>
                <div
                  className="mt-0.5 text-muted-foreground text-xs outline-none"
                  contentEditable
                  suppressContentEditableWarning
                  onBlur={(e) =>
                    onChange({
                      ...resumeData,
                      header: { ...resumeData.header, intention: e.currentTarget.innerText.trim() },
                    })
                  }
                >
                  {resumeData.header.intention}
                </div>
              </div>
            </EditableBlock>
            {resumeData.sections.map((section, index) => {
              // 🌟 跳过完全为空的模块（标题和内容都为空）
              const hasTitle = section.title && section.title.trim()
              const hasContent = section.content && section.content.trim()
              if (!hasTitle && !hasContent) {
                return null
              }
              
              return (
                <EditableBlock
                  key={section.id}
                  id={section.id}
                  hoveredBlock={hoveredBlock}
                  setHoveredBlock={setHoveredBlock}
                >
                  <EditableSection
                    section={section}
                    isMatched={matchedSectionIds.includes(section.id)}
                    onSelectText={onTextSelect}
                    onCommit={handleSectionCommit}
                    onDragStart={setDraggingSectionId}
                    onDropTo={handleDropTo}
                    onMoveUp={() => moveSection(index, -1)}
                    onMoveDown={() => moveSection(index, 1)}
                    findText={findText}
                    currentMatchIndex={currentMatchIndex}
                    onRegisterMatch={registerMatch}
                  />
                </EditableBlock>
              )
            })}
            
            {/* 🌟 添加自定义模块按钮 */}
            <button
              onClick={handleAddSection}
              className="w-full mt-4 py-3 border-2 border-dashed border-gray-300 rounded-lg text-gray-500 hover:border-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-all duration-200 flex items-center justify-center gap-2 text-sm font-medium"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              添加自定义模块
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function EditableBlock({
  id,
  hoveredBlock,
  setHoveredBlock,
  children,
}: {
  id: string
  hoveredBlock: string | null
  setHoveredBlock: (id: string | null) => void
  children: ReactNode
}) {
  const isHovered = hoveredBlock === id
  return (
    <div
      className={`transition-all rounded px-1 -mx-1 ${
        isHovered ? "bg-muted/50 ring-1 ring-dashed ring-border" : ""
      }`}
      onMouseEnter={() => setHoveredBlock(id)}
      onMouseLeave={() => setHoveredBlock(null)}
    >
      {children}
    </div>
  )
}

function AICopilotColumn({
  job,
  onUpdateJob,
  selectedText,
  onPolish,
  qaReport,
}: {
  job: JobData
  onUpdateJob: (job: JobData) => void
  selectedText: string
  onPolish: (instruction: string) => Promise<void>
  qaReport?: any
}) {
  const [instruction, setInstruction] = useState("")
  const [isPolishing, setIsPolishing] = useState(false)
  const [myReview, setMyReview] = useState(job?.myReview || "")
  const [isSavingReview, setIsSavingReview] = useState(false)
  const [greetingMsg, setGreetingMsg] = useState(job?.greetingMsg || "")
  const [isSavingGreeting, setIsSavingGreeting] = useState(false)
  const skillsText = useMemo(() => job?.skillReq || "暂无数据", [job?.skillReq])
  const rewriteAnnotations = useMemo(
    () => parseAiRewriteAnnotations(job?.aiRewriteJson || ""),
    [job?.aiRewriteJson],
  )

  // 🌟 从混合了 Markdown 和 JSON 的文本中强行提取改写说明和缺失数据
  const rewriteLogicData = useMemo(() => {
    if (!job?.aiRewriteJson) return { rationaleItems: [] as { label: string; rationale: string }[], missingItems: [] as { question: string }[], hasAny: false }
    
    const rationaleItems: { label: string; rationale: string }[] = []
    let missingItems: { question: string }[] = []

    try {
      const rawText = job.aiRewriteJson;
      // 🚀 核心：用正则直接匹配字符串中 { "rewrite_rationale" ... } 这一段 JSON，无视前面的简历正文
      const jsonMatch = rawText.match(/\{[\s\S]*"rewrite_rationale"[\s\S]*\}/);
      
      let parsedData = null;
      if (jsonMatch) {
        parsedData = JSON.parse(jsonMatch[0]); // 只解析提取出来的 JSON 块
      } else {
        // 如果正则没抓到，尝试整体解析兜底
        parsedData = JSON.parse(rawText);
      }

      if (parsedData && typeof parsedData === 'object') {
        // 1. 提取改写理由
        if (parsedData.rewrite_rationale && typeof parsedData.rewrite_rationale === 'object') {
          Object.entries(parsedData.rewrite_rationale).forEach(([key, val]) => {
            rationaleItems.push({ label: key, rationale: String(val) });
          });
        }
        
        // 2. 提取数据补充
        if (Array.isArray(parsedData.missing_data_requests)) {
          missingItems = parsedData.missing_data_requests.map((r: any) => ({ 
            question: typeof r === 'string' ? r : (r?.question || String(r)) 
          }));
        }
      }
    } catch (e) {
      console.warn("⚠️ 从混合文本中提取 AI改写JSON 失败:", e);
    }

    return { rationaleItems, missingItems, hasAny: rationaleItems.length > 0 || missingItems.length > 0 };
  }, [job?.aiRewriteJson]);

  // 同步 job.myReview 到本地状态
  useEffect(() => {
    setMyReview(job?.myReview || "")
    setGreetingMsg(job?.greetingMsg || "")
  }, [job?.id, job?.myReview, job?.greetingMsg])

  const handlePolish = async () => {
    if (!selectedText || !instruction.trim()) return
    setIsPolishing(true)
    try {
      await onPolish(instruction.trim())
    } finally {
      setIsPolishing(false)
    }
  }

  const handleSaveReview = async () => {
    if (!job?.id) {
      alert("❌ 错误：无法获取当前岗位 ID")
      return
    }
    
    setIsSavingReview(true)
    try {
      const response = await fetch("http://127.0.0.1:8000/api/update_review_comments", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          job_id: job.id, 
          comments: myReview 
        }),
      })
      
      const data = await response.json()
      
      if (!response.ok) {
        alert("❌ 保存失败：" + (data.detail || data.msg || "未知错误"))
        return
      }
      
      if (data.status === "success") {
        // 更新全局状态
        if (onUpdateJob && job) {
          onUpdateJob({
            ...job,
            myReview: myReview
          })
        }
        alert("✅ 复核意见已保存到飞书")
      } else {
        alert("❌ 保存失败：" + (data.message || "未知错误"))
      }
    } catch (error) {
      alert("❌ 网络错误，请检查后端是否运行")
      console.error("保存复核意见错误:", error)
    } finally {
      setIsSavingReview(false)
    }
  }

  const handleSaveGreeting = async () => {
    if (!job?.id) {
      alert("❌ 错误：无法获取当前岗位 ID")
      return
    }
    
    setIsSavingGreeting(true)
    try {
      const response = await fetch("http://127.0.0.1:8000/api/update_greeting", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          job_id: job.id, 
          greeting: greetingMsg 
        }),
      })
      
      const data = await response.json()
      
      if (!response.ok) {
        alert("❌ 保存失败：" + (data.detail || data.msg || "未知错误"))
        return
      }
      
      if (data.status === "success") {
        if (onUpdateJob && job) {
          onUpdateJob({
            ...job,
            greetingMsg: greetingMsg
          })
        }
        alert("✅ 打招呼语已保存到飞书")
      } else {
        alert("❌ 保存失败：" + (data.message || "未知错误"))
      }
    } catch (error) {
      alert("❌ 网络错误，请检查后端是否运行")
      console.error("保存打招呼语错误:", error)
    } finally {
      setIsSavingGreeting(false)
    }
  }

  return (
    <div className="h-full bg-card flex flex-col relative">
      <div className="px-3 py-2 border-b border-border shrink-0">
        <h3 className="font-medium text-xs text-foreground flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5" />
          AI Copilot
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        <Accordion
          type="multiple"
          defaultValue={["ai_diagnosis", "rewrite_notes", "ai_rewrite_logic", "qa_report", "greeting", "my_review"]}
          className="w-full"
        >
          <AccordionItem value="ai_diagnosis">
            <AccordionTrigger className="text-xs py-2 hover:no-underline bg-violet-50 dark:bg-violet-950/20 px-2 rounded">
              🔬 AI 专家诊断
            </AccordionTrigger>
            <AccordionContent className="pt-2 space-y-3">
              <AiGradeDashboard job={job} />
              {job.aiEvaluationDetail ? (
              <div className="space-y-1">
                <h4 className="text-[10px] font-semibold text-violet-700 uppercase tracking-wide">各维度评分依据</h4>
                <div className="text-[11px] text-muted-foreground leading-relaxed whitespace-pre-line bg-violet-50/50 border border-violet-100 rounded-md p-2.5 max-h-64 overflow-y-auto">
                  {job.aiEvaluationDetail}
                </div>
              </div>
            ) : (
              <p className="text-[11px] text-muted-foreground py-1">暂无诊断数据，请先执行 AI 评估</p>
            )}

            {job.atsAbilityAnalysis && (
                <div className="border border-teal-200 bg-teal-50/50 rounded-md p-2.5">
                  <h4 className="text-[10px] font-semibold text-teal-700 mb-1 uppercase tracking-wide">📚 核心能力词典</h4>
                  <div className="text-[11px] text-muted-foreground whitespace-pre-line leading-relaxed">
                    {job.atsAbilityAnalysis
                      .replace(/(?:[,，。;；]?\s*)(必考词|加分词|词汇重合度|缺失核心词|表达错位)/g, '\n$1')
                      .replace(/(?:[,，。;；]?\s*)(【提取技能词】)/g, '\n\n$1')
                      .trim()}
                  </div>
                </div>
              )}
              {job.strongFitAssessment && (
                <div className="border border-emerald-200 bg-emerald-50/50 rounded-md p-2.5">
                  <h4 className="text-[10px] font-semibold text-emerald-700 mb-1 uppercase tracking-wide">✅ 高杠杆匹配点</h4>
                  <div className="text-[11px] text-muted-foreground whitespace-pre-line leading-relaxed">{job.strongFitAssessment}</div>
                </div>
              )}
              {/* 🌟 移入此处的理想画像，采用靛蓝色 (Indigo) 主题 */}
              {job.dreamPicture && (
                <div className="border border-indigo-200 bg-indigo-50/50 rounded-md p-2.5">
                  <h4 className="text-[10px] font-semibold text-indigo-700 mb-1 uppercase tracking-wide">🎯 理想画像与能力信号</h4>
                  <div className="text-[11px] text-muted-foreground whitespace-pre-line leading-relaxed">{job.dreamPicture}</div>
                </div>
              )}
              {job.riskRedFlags && (
                <div className="border border-red-200 bg-red-50/50 rounded-md p-2.5">
                  <h4 className="text-[10px] font-semibold text-red-700 mb-1 uppercase tracking-wide">⚠️ 致命硬伤与毒点</h4>
                  <div className="text-[11px] text-muted-foreground whitespace-pre-line leading-relaxed">
                    {/* 🌟 正则：将连在一起的“恶劣后果”强行另起一行 */}
                    {job.riskRedFlags.replace(/\s*(恶劣后果(?:：|:)?)/g, '\n\n$1').trim()}
                  </div>
                </div>
              )}
              {job.deepActionPlan && (
                <div className="border border-blue-200 bg-blue-50/50 rounded-md p-2.5">
                  <h4 className="text-[10px] font-semibold text-blue-700 mb-1 uppercase tracking-wide">🚀 破局行动计划</h4>
                  <div className="text-[11px] text-muted-foreground whitespace-pre-line leading-relaxed">
                    {/* 🌟 正则：将连在一起的“项目重新包装”强行另起一行 */}
                    {job.deepActionPlan.replace(/\s*(项目重新包装(?:：|:)?)/g, '\n\n$1').trim()}
                  </div>
                </div>
              )}
              {/* 🌟 专门的“简历改写理由及数据补充”模块 */}
              {rewriteLogicData.hasAny && (
                <div className="border border-indigo-200 bg-indigo-50/40 rounded-md p-2.5 mt-3 shadow-sm">
                  <h4 className="text-[10px] font-bold text-indigo-800 mb-2 uppercase tracking-wide flex items-center gap-1.5">
                    📝 简历改写理由及数据补充
                  </h4>
                  <div className="space-y-3">
                    
                    {/* 1. 改写理由 */}
                    {rewriteLogicData.rationaleItems.length > 0 && (
                      <div className="space-y-1.5">
                        <div className="text-[11px] font-semibold text-indigo-900/90 bg-indigo-100/50 inline-block px-1.5 py-0.5 rounded">改写依据与逻辑：</div>
                        <ul className="list-disc pl-4 space-y-2 text-[11px] text-muted-foreground leading-relaxed">
                          {rewriteLogicData.rationaleItems.map((item, idx) => (
                            <li key={idx}>
                              <span className="font-semibold text-indigo-700 mr-1">[{item.label}]</span>
                              {item.rationale}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    
                    {/* 2. 数据补充 */}
                    {rewriteLogicData.missingItems.length > 0 && (
                      <div className="space-y-1.5 pt-2 border-t border-indigo-100/60">
                        <div className="text-[11px] font-semibold text-orange-700 bg-orange-100/50 inline-block px-1.5 py-0.5 rounded flex items-center gap-1 w-max">
                          💡 简历待补充信息：
                        </div>
                        <ul className="list-disc pl-4 space-y-1.5 text-[11px] text-orange-800/80 leading-relaxed">
                          {rewriteLogicData.missingItems.map((item, idx) => (
                            <li key={idx} className="font-medium">{item.question}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                  </div>
                </div>
              )}

            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="qa_report">
            <AccordionTrigger className="text-xs py-2 hover:no-underline bg-purple-50 dark:bg-purple-950/20 px-2 rounded">
              🔍 二次质检报告 (QA)
            </AccordionTrigger>
            <AccordionContent className="pt-2">
              {!qaReport ? (
                <p className="text-[11px] text-muted-foreground leading-relaxed py-2">
                  暂无质检数据，请点击中间栏的"再次AI评估简历"按钮
                </p>
              ) : (
                <div className="space-y-3">
                  {qaReport.match_verification && (
                    <div className="border border-border rounded-md p-2.5">
                      <h4 className="text-xs font-semibold text-green-700 dark:text-green-400 mb-1.5">✅ 已达成匹配点</h4>
                      <ul className="text-[11px] text-muted-foreground space-y-1 leading-relaxed">
                        {qaReport.match_verification.achieved_points?.map((point: string, idx: number) => (
                          <li key={idx} className="whitespace-pre-line">{point}</li>
                        ))}
                      </ul>
                      <h4 className="text-xs font-semibold text-orange-700 dark:text-orange-400 mt-3 mb-1.5">⚠️ 缺失匹配点</h4>
                      <ul className="text-[11px] text-muted-foreground space-y-1 leading-relaxed">
                        {qaReport.match_verification.missing_points?.map((point: string, idx: number) => (
                          <li key={idx} className="whitespace-pre-line">{point}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {qaReport.hallucination_check && (
                    <div className="border border-border rounded-md p-2.5">
                      <h4 className="text-xs font-semibold text-red-700 dark:text-red-400 mb-1.5">🚨 过度包装检查</h4>
                      <ul className="text-[11px] text-muted-foreground space-y-1 leading-relaxed">
                        {qaReport.hallucination_check.map((item: string, idx: number) => (
                          <li key={idx} className="whitespace-pre-line">{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {qaReport.human_action_items && qaReport.human_action_items.length > 0 && (
                    <div className="border border-purple-200 dark:border-purple-800 bg-purple-50/50 dark:bg-purple-950/30 rounded-md p-2.5">
                      <h4 className="text-xs font-semibold text-purple-700 dark:text-purple-400 mb-1.5">📋 人工待办清单</h4>
                      <ul className="text-[11px] text-muted-foreground space-y-1.5 leading-relaxed">
                        {qaReport.human_action_items.map((item: string, idx: number) => (
                          <li key={idx} className="whitespace-pre-line font-mono">{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="greeting">
            <AccordionTrigger className="text-xs py-2 hover:no-underline">
              打招呼语
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-2">
                {/* 🌟 相对定位容器，用于字数统计的绝对定位 */}
                <div className="relative w-full">
                  <Textarea
                    className="min-h-[200px] text-[11px] leading-relaxed pb-8"
                    value={greetingMsg}
                    onChange={(e) => setGreetingMsg(e.target.value)}
                    placeholder="暂无数据"
                  />
                  {/* 🌟 字数统计标签 - 右下角绝对定位 */}
                  <div className="absolute bottom-2 right-2 text-xs text-gray-400 pointer-events-none select-none">
                    {greetingMsg.length} 字
                  </div>
                </div>
                {/* 🌟 两个等宽按钮布局 */}
                <div className="flex w-full gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 h-7 text-xs gap-1.5 bg-gray-50 hover:bg-gray-100"
                    onClick={handleSaveGreeting}
                    disabled={isSavingGreeting}
                  >
                    <Save className="h-3 w-3" />
                    {isSavingGreeting ? "保存中..." : "保存"}
                  </Button>
                  <Button
                    variant="default"
                    size="sm"
                    className="flex-1 h-7 text-xs gap-1.5"
                    onClick={() => {
                      navigator.clipboard.writeText(greetingMsg)
                      alert("✅ 已复制到剪贴板")
                    }}
                  >
                    <Copy className="h-3 w-3" />
                    复制
                  </Button>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="my_review">
            <AccordionTrigger className="text-xs py-2 hover:no-underline">
              我的复核
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-2">
                <Textarea
                  className="min-h-[150px] text-[11px] leading-relaxed"
                  value={myReview}
                  onChange={(e) => setMyReview(e.target.value)}
                  placeholder="在这里记录你对这个岗位的复核意见..."
                />
                <Button
                  variant="default"
                  size="sm"
                  className="w-full h-7 text-xs gap-1.5"
                  onClick={handleSaveReview}
                  disabled={isSavingReview}
                >
                  <Save className="h-3 w-3" />
                  {isSavingReview ? "保存中..." : "保存到飞书"}
                </Button>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>
    </div>
  )
}