"use client"

import Link from "next/link"
import { Briefcase, Mic, Beaker } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { GlobalView } from "@/app/page"

interface TopNavBarProps {
  currentView: GlobalView
  onMainTabChange: (tab: "immersive" | "interview") => void
  statusCounts: Record<string, number>
}

export function TopNavBar({
  currentView,
  onMainTabChange,
  statusCounts,
}: TopNavBarProps) {
  const isImmersive = currentView !== "interview-camp"
  const sortedStatusEntries = Object.entries(statusCounts).sort((a, b) => b[1] - a[1])

  return (
    <header className="h-12 border-b border-border bg-card flex items-center justify-between px-4 shrink-0">
      {/* Left: Logo & 策略大盘入口 */}
      <div className="flex items-center gap-6">
        {/* 🌟 用 Link 包裹 Logo，点击即可回首页 */}
        <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
          <Briefcase className="h-5 w-5 text-primary" />
          <span className="font-semibold text-foreground text-sm">JobHunter AI</span>
        </Link>
        
        {/* 🌟 新增的策略大盘入口 */}
        <Link 
          href="/strategy" 
          className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-primary transition-colors"
        >
          <Beaker className="h-4 w-4" />
          策略大盘
        </Link>
      </div>

      {/* Center: Main Tabs */}
      <div className="flex items-center gap-1 bg-muted rounded-lg p-1">
        <Button
          variant={isImmersive ? "default" : "ghost"}
          size="sm"
          onClick={() => onMainTabChange("immersive")}
          className="h-7 px-3 text-xs gap-1.5"
        >
          <Briefcase className="h-3.5 w-3.5" />
          沉浸工作台
        </Button>
        <Button
          variant={!isImmersive ? "default" : "ghost"}
          size="sm"
          onClick={() => onMainTabChange("interview")}
          className="h-7 px-3 text-xs gap-1.5"
        >
          <Mic className="h-3.5 w-3.5" />
          面试训练营
        </Button>
      </div>

      {/* Right: Status Counts */}
      <div className="flex items-center gap-2 text-xs">
        {sortedStatusEntries.length === 0 && (
          <span className="text-muted-foreground">暂无状态数据</span>
        )}
        {sortedStatusEntries.map(([label, count], index) => (
          <div key={label} className="flex items-center gap-2">
            <StatusBadge label={label} count={count} />
            {index < sortedStatusEntries.length - 1 && (
              <span className="text-muted-foreground">|</span>
            )}
          </div>
        ))}
      </div>
    </header>
  )
}

function StatusBadge({
  label,
  count,
}: {
  label: string
  count: number
}) {
  return (
    <span className="flex items-center gap-1">
      <span className="text-muted-foreground">{label}:</span>
      <span className="font-semibold text-foreground">{count}</span>
    </span>
  )
}