"use client"

import { useRouter } from "next/navigation" // 🌟 引入 Next.js 的路由工具
import { TopNavBar } from "@/components/dashboard/top-nav-bar"
import StrategyLab from "../../components/dashboard/strategy-lab"

export default function StrategyPage() {
  const router = useRouter() // 🌟 初始化路由

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <TopNavBar 
        currentView={"immersive" as any}
        onMainTabChange={() => {
          // 🌟 点击“沉浸工作台”或“面试训练营”时，强制跳转回主页
          router.push("/")
        }} 
        statusCounts={{}} 
      />
      <div className="flex-1 overflow-hidden">
        <StrategyLab />
      </div>
    </div>
  )
}