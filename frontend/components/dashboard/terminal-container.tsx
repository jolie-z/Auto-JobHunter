"use client"

import { useTerminalStore } from "@/store/terminal-store"
import { LiveTaskTerminal } from "./live-task-terminal"
import { Button } from "@/components/ui/button"
import { Minimize2, X } from "lucide-react"

interface TerminalContainerProps {
  onComplete?: () => void
  onSseMessage?: (data: any) => void
}

export function TerminalContainer({ onComplete, onSseMessage }: TerminalContainerProps) {
  const { mode, minimize, closeTerminal1 } = useTerminalStore()

  if (mode === 'minimize') return null

  return (
    <div className="fixed inset-0 z-40 pointer-events-none">
      <div className="absolute top-0 right-0 bottom-0 w-1/3 min-w-[380px] pointer-events-auto">
        <div className="h-full bg-white border-l border-gray-200 shadow-2xl flex flex-col overflow-hidden">

          {/* 工具栏 */}
          <div className="h-12 px-4 flex items-center justify-between border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white shrink-0">
            <span className="text-sm font-medium text-gray-800">任务控制台</span>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-gray-500 hover:text-gray-700 hover:bg-gray-100"
                onClick={minimize}
                title="最小化"
              >
                <Minimize2 className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-gray-500 hover:text-red-600 hover:bg-red-50"
                onClick={closeTerminal1}
                title="关闭"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* 终端内容区 */}
          <div className="flex-1 min-h-0 overflow-hidden">
            <LiveTaskTerminal
              onComplete={onComplete}
              onMinimize={minimize}
              onClose={closeTerminal1}
              onSseMessage={onSseMessage}
              showInternalHeader={false}
            />
          </div>

        </div>
      </div>
    </div>
  )
}
