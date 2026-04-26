"use client"

import { Mic, Rocket, MessageSquare, Target, Clock } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function InterviewCamp() {
  return (
    <div className="h-full flex flex-col items-center justify-center bg-gradient-to-b from-muted/30 to-muted/50 p-8">
      <Card className="max-w-lg w-full border-dashed border-2 bg-card/50 backdrop-blur-sm">
        <CardContent className="pt-12 pb-10 flex flex-col items-center text-center">
          {/* Illustration */}
          <div className="relative mb-6">
            <div className="w-24 h-24 rounded-full bg-primary/10 flex items-center justify-center">
              <Mic className="h-12 w-12 text-primary" />
            </div>
            <div className="absolute -top-2 -right-2 w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center animate-bounce">
              <Rocket className="h-4 w-4 text-amber-600" />
            </div>
          </div>

          {/* Title */}
          <h2 className="text-xl font-bold text-foreground mb-2">
            面试训练营开发中...
          </h2>
          <p className="text-sm text-muted-foreground mb-6 max-w-sm">
            AI 驱动的模拟面试系统即将上线，助你从容应对每一场面试挑战
          </p>

          {/* Feature Preview */}
          <div className="grid grid-cols-3 gap-4 mb-6 w-full">
            <FeatureCard icon={MessageSquare} title="AI 模拟面试" />
            <FeatureCard icon={Target} title="精准题库" />
            <FeatureCard icon={Clock} title="限时答题" />
          </div>

          {/* CTA */}
          <Button variant="outline" size="sm" className="gap-2">
            <Clock className="h-3.5 w-3.5" />
            敬请期待
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

function FeatureCard({
  icon: Icon,
  title,
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
}) {
  return (
    <div className="flex flex-col items-center gap-2 p-3 rounded-lg bg-muted/50">
      <Icon className="h-5 w-5 text-muted-foreground" />
      <span className="text-xs text-muted-foreground">{title}</span>
    </div>
  )
}
