import { create } from 'zustand'

export type TerminalMode = 'minimize' | 'single' | 'dual'

interface TerminalState {
  mode: TerminalMode
  isTerminal1Active: boolean
  isTerminal2Active: boolean
  
  // Actions
  openSingle: () => void
  openDual: () => void
  minimize: () => void
  closeTerminal1: () => void
  closeTerminal2: () => void
  restoreFromMinimize: () => void
}

export const useTerminalStore = create<TerminalState>((set, get) => ({
  mode: 'minimize',
  isTerminal1Active: false,
  isTerminal2Active: false,

  openSingle: () => set({ 
    mode: 'single', 
    isTerminal1Active: true,
    isTerminal2Active: false 
  }),

  openDual: () => set({ 
    mode: 'dual', 
    isTerminal1Active: true,
    isTerminal2Active: true 
  }),

  minimize: () => set({ mode: 'minimize' }),

  closeTerminal1: () => {
    const { isTerminal2Active } = get()
    if (isTerminal2Active) {
      // 如果终端2还开着，切换到单窗口模式（只显示终端2）
      set({ 
        mode: 'single',
        isTerminal1Active: false 
      })
    } else {
      // 两个都关了，回到最小化
      set({ 
        mode: 'minimize',
        isTerminal1Active: false 
      })
    }
  },

  closeTerminal2: () => {
    const { isTerminal1Active } = get()
    if (isTerminal1Active) {
      // 如果终端1还开着，切换到单窗口模式（只显示终端1）
      set({ 
        mode: 'single',
        isTerminal2Active: false 
      })
    } else {
      // 两个都关了，回到最小化
      set({ 
        mode: 'minimize',
        isTerminal2Active: false 
      })
    }
  },

  restoreFromMinimize: () => {
    const { isTerminal1Active, isTerminal2Active } = get()
    
    if (isTerminal1Active && isTerminal2Active) {
      // 之前是双开，恢复双开
      set({ mode: 'dual' })
    } else if (isTerminal1Active || isTerminal2Active) {
      // 之前是单开，恢复单开
      set({ mode: 'single' })
    } else {
      // 都没开过，默认打开终端1
      set({ 
        mode: 'single',
        isTerminal1Active: true 
      })
    }
  },
}))
