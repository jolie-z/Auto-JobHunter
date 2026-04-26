"use client"

import { Bot } from "lucide-react"
import { useTerminalStore } from "@/store/terminal-store"

export function FloatingBadge() {
  const { mode, restoreFromMinimize } = useTerminalStore()

  if (mode !== 'minimize') return null

  return (
    <button
      onClick={restoreFromMinimize}
      className="fixed bottom-6 right-6 z-50 bg-gradient-to-r from-blue-600 to-purple-600 text-white p-4 rounded-full shadow-[0_4px_20px_rgb(0,0,0,0.15)] hover:shadow-[0_6px_30px_rgb(0,0,0,0.25)] transition-all hover:scale-110 group"
      aria-label="打开终端控制台"
    >
      <Bot className="h-6 w-6 group-hover:animate-pulse" />
      <span className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full animate-pulse border-2 border-white" />
    </button>
  )
}
