# 全局悬浮多开控制台系统文档

## 🎯 系统概述

实现了一个全局悬浮的多开终端控制台系统，支持单窗口和双窗口并排模式，可随时最小化而不影响后台爬虫进程的运行。

## 📁 文件结构

```
pronted design/
├── store/
│   └── terminal-store.ts          # Zustand 全局状态管理
├── components/dashboard/
│   ├── floating-badge.tsx         # 右下角悬浮浮标
│   ├── terminal-container.tsx     # 终端容器（单/双窗口布局）
│   └── live-task-terminal.tsx     # 终端实例组件（已适配）
└── app/
    └── page.tsx                   # 主页面集成
```

## 🔧 核心组件说明

### 1. **全局状态管理** (`terminal-store.ts`)

使用 Zustand 管理全局终端状态，包含三种模式：

- `minimize`: 最小化为浮标
- `single`: 单窗口模式
- `dual`: 双窗口模式

**状态字段：**
```typescript
{
  mode: TerminalMode                // 当前模式
  isTerminal1Active: boolean        // 终端1是否激活
  isTerminal2Active: boolean        // 终端2是否激活
}
```

**核心 Actions：**
- `openSingle()`: 打开单窗口模式
- `openDual()`: 打开双窗口模式
- `minimize()`: 最小化到浮标
- `closeTerminal1()`: 关闭终端1
- `closeTerminal2()`: 关闭终端2
- `restoreFromMinimize()`: 从最小化状态恢复

### 2. **浮标组件** (`floating-badge.tsx`)

**功能：**
- 仅在 `mode === 'minimize'` 时显示
- 固定在页面右下角
- 点击后调用 `restoreFromMinimize()` 恢复之前的状态

**特性：**
- 渐变色背景（蓝紫渐变）
- 带有绿色脉冲指示灯
- Hover 时放大动画

### 3. **终端容器** (`terminal-container.tsx`)

**功能：**
- 管理单/双窗口布局
- 根据 `mode` 动态调整宽度（单窗口 35vw，双窗口 65vw）
- 使用 CSS `hidden` 类而非条件渲染来隐藏终端，**确保组件不被卸载**

**布局逻辑：**

**单窗口模式：**
- 显示全局工具栏（包含 "+" 增加窗口、"_" 最小化按钮）
- 渲染一个终端实例
- 宽度占屏幕 35%

**双窗口模式：**
- 使用 Grid 布局左右并排
- 每个终端有独立工具栏（"_" 最小化、"x" 关闭）
- 宽度占屏幕 65%

**关键代码片段：**
```tsx
{/* 使用 hidden 而非条件渲染 */}
<div className={`h-full ${!isTerminal1Active ? 'hidden' : ''}`}>
  <LiveTaskTerminal {...props} />
</div>
```

### 4. **终端实例组件** (`live-task-terminal.tsx`)

**新增 Props：**
```typescript
{
  onMinimize?: () => void    // 最小化回调
  onClose?: () => void       // 关闭回调
  showToolbar?: boolean      // 是否显示独立工具栏
}
```

**适配改动：**
- 支持两种标题栏模式：
  - `showToolbar=true`: 显示完整工具栏（带最小化/关闭按钮）
  - `showToolbar=false`: 显示简化标题栏（仅显示标题和连接状态）
- 移除了固定定位样式，改为 `h-full w-full` 适配容器布局

## 🎮 交互流程

### 初始状态
1. 页面加载时，`mode = 'minimize'`，显示右下角浮标
2. 点击浮标 → 调用 `restoreFromMinimize()`
3. 如果两个终端都未激活，默认打开终端1（单窗口模式）

### 单窗口模式
1. 点击 "+" 按钮 → 调用 `openDual()`，进入双窗口模式
2. 点击 "_" 按钮 → 调用 `minimize()`，回到浮标状态
3. **关键**：最小化时终端组件不卸载，仅通过 CSS `hidden` 隐藏

### 双窗口模式
1. 点击任一终端的 "_" 按钮 → 调用 `minimize()`，整个容器隐藏
2. 点击终端1的 "x" 按钮 → 调用 `closeTerminal1()`
   - 如果终端2还开着 → 切换到单窗口模式（只显示终端2）
   - 如果终端2也关了 → 回到最小化状态
3. 点击终端2的 "x" 按钮 → 同理

### 状态恢复
1. 从最小化状态恢复时，根据 `isTerminal1Active` 和 `isTerminal2Active` 判断：
   - 两个都激活 → 恢复双窗口模式
   - 只有一个激活 → 恢复单窗口模式
   - 都未激活 → 默认打开终端1

## 🔑 核心设计原则

### 1. **隐藏而不卸载**
使用 CSS `hidden` 类而非条件渲染（`{condition && <Component />}`），确保：
- SSE 连接不断开
- 日志持续接收
- 状态完整保留

```tsx
{/* ✅ 正确做法 */}
<div className={!isActive ? 'hidden' : ''}>
  <LiveTaskTerminal />
</div>

{/* ❌ 错误做法 */}
{isActive && <LiveTaskTerminal />}
```

### 2. **状态集中管理**
所有终端状态由 Zustand store 统一管理，避免 props drilling 和状态不一致。

### 3. **独立性与复用性**
- `LiveTaskTerminal` 组件保持高度内聚，可独立使用
- 通过 props 适配不同场景（独立使用 vs 容器内使用）

## 📦 使用示例

### 在页面中集成
```tsx
import { FloatingBadge } from "@/components/dashboard/floating-badge"
import { TerminalContainer } from "@/components/dashboard/terminal-container"

export default function Page() {
  return (
    <div>
      {/* 你的页面内容 */}
      
      {/* 全局终端系统 */}
      <FloatingBadge />
      <TerminalContainer onComplete={handleTaskComplete} />
    </div>
  )
}
```

### 直接使用终端组件（独立模式）
```tsx
<LiveTaskTerminal
  title="独立终端"
  placeholder="输入命令..."
  onComplete={() => console.log('完成')}
/>
```

## 🚀 后端适配要求

后端需要支持前端传递的 `task_id`：

```typescript
// 前端发送
fetch("/api/chat/command", {
  method: "POST",
  body: JSON.stringify({ 
    command: "帮我抓取Boss直聘第1页",
    task_id: "task_1234567890_abc123"  // 前端生成的唯一ID
  })
})

// 后端返回
{ task_id: "task_1234567890_abc123" }

// SSE 推送时使用该 task_id
GET /api/tasks/logs?task_id=task_1234567890_abc123
```

## 🎨 样式定制

### 浮标样式
修改 `floating-badge.tsx` 中的 className：
```tsx
className="fixed bottom-6 right-6 z-50 bg-gradient-to-r from-blue-600 to-purple-600 ..."
```

### 容器宽度
修改 `terminal-container.tsx` 中的宽度变量：
```tsx
const containerWidth = isDualMode ? 'w-[65vw]' : 'w-[35vw]'
```

## 🐛 常见问题

### Q: 最小化后 SSE 连接断开？
A: 检查是否使用了条件渲染。必须使用 CSS `hidden` 类而非 `{condition && <Component />}`。

### Q: 关闭终端后无法重新打开？
A: 检查 `isTerminal1Active` 和 `isTerminal2Active` 状态是否正确更新。

### Q: 双窗口模式下只显示一个终端？
A: 确保 `openDual()` 同时设置了 `isTerminal1Active: true` 和 `isTerminal2Active: true`。

## 📝 待优化项

1. 添加拖拽调整窗口大小功能
2. 支持更多终端实例（3个、4个）
3. 添加终端标签页切换模式
4. 持久化终端状态到 localStorage
5. 添加终端主题切换功能
