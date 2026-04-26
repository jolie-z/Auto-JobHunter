"use client"

import React, { useState, useEffect, useRef } from 'react'
import { FileText, MessageSquare, Plus, Save, CheckCircle, Circle, RefreshCw, Play, Terminal, Trash2, Upload, Layout, Download, Edit2, Settings, ChevronDown, ChevronUp } from 'lucide-react'

type TemplateItem = {
  name: string
  size: number
  is_default: boolean
  variables?: string[]
  tags?: string[]
}

type StrategyItem = {
  record_id?: string;
  name: string;
  content: string;
  status: string;
}

function TemplatePreviewImage({ name, cacheKey }: { name: string; cacheKey: number }) {
  const [status, setStatus] = useState<'loading' | 'loaded' | 'error'>('loading')
  const [retryCount, setRetryCount] = useState(0) // 🌟 新增：重试计数器

  useEffect(() => { 
    setStatus('loading') 
    setRetryCount(0) // 🌟 切换模板或重新上传时，清空重试次数
  }, [name, cacheKey])

  // 🌟 动态 URL：拼接 retry 参数，强制浏览器忽略缓存发起新请求
  const src = `http://127.0.0.1:8000/api/templates/preview/${encodeURIComponent(name)}?t=${cacheKey}&retry=${retryCount}`

  return (
    <div className="relative">
      {status === 'loading' && (
        <div className="flex flex-col items-center justify-center h-48 bg-gray-50 rounded-lg border border-dashed border-gray-200 gap-2 text-gray-300 animate-pulse">
          <FileText size={36} />
          <span className="text-xs">预览图生成中...</span>
        </div>
      )}
      {status === 'error' && (
        <div className="flex flex-col items-center justify-center h-48 bg-gray-50 rounded-lg border border-dashed border-gray-200 gap-2 text-gray-400">
          <FileText size={36} className="opacity-25" />
          <p className="text-xs">预览图生成失败或超时</p>
          <p className="text-[10px] text-gray-300">请检查后端日志，或手动刷新页面</p>
        </div>
      )}
      <img
        key={`${name}-${retryCount}`} // 🌟 核心：利用 key 的变化，强制 React 重新挂载 img 标签
        src={src}
        alt={`${name} 预览`}
        className={`w-full rounded-lg border border-gray-200 shadow-md object-contain transition-opacity duration-300 ${
          status === 'loaded' ? 'opacity-100' : 'opacity-0 h-0 absolute'
        }`}
        onLoad={() => setStatus('loaded')}
        onError={() => {
          // 🌟 轮询引擎：如果加载失败（404），且重试少于 10 次，则 2 秒后发起下一次请求
          if (retryCount < 10) {
            setTimeout(() => {
              setRetryCount(prev => prev + 1)
            }, 2000)
          } else {
            // 重试 10 次（20多秒）依然失败，才真正判定为 error
            setStatus('error')
          }
        }}
      />
    </div>
  )
}

export default function StrategyLab() {
  const [activeTab, setActiveTab] = useState<'resume' | 'prompt' | 'template'>('resume')
  const [resumes, setResumes] = useState<StrategyItem[]>([])
  const [prompts, setPrompts] = useState<StrategyItem[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editingItem, setEditingItem] = useState<StrategyItem | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isParsing, setIsParsing] = useState(false)

  // 🌟 修复 1：JD 缓存竞态问题（加入加载锁，防止空状态覆盖本地缓存）
  const [testJd, setTestJd] = useState("")
  const [isJdLoaded, setIsJdLoaded] = useState(false)

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('jobhunter_test_jd')
      if (saved) setTestJd(saved)
      setIsJdLoaded(true) // 标记：本地数据已读取完毕
    }
  }, [])

  useEffect(() => {
    // 只有当本地数据读取完毕后，用户的输入才会去覆盖本地存储
    if (isJdLoaded && typeof window !== 'undefined') {
      localStorage.setItem('jobhunter_test_jd', testJd)
    }
  }, [testJd, isJdLoaded])

  const [testResult, setTestResult] = useState("")
  const [testMode, setTestMode] = useState<'evaluate' | 'rewrite' | 'greeting'>('evaluate')
  const [isTesting, setIsTesting] = useState(false)
  const [resultCache, setResultCache] = useState<Record<string, string>>({})

  const [togglingResumeId, setTogglingResumeId] = useState<string | null>(null)
  const [templates, setTemplates] = useState<TemplateItem[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateItem | null>(null)
  const tplInputRef = useRef<HTMLInputElement>(null)
  const tplUpdateRef = useRef<HTMLInputElement>(null)
  const [isUploadingTpl, setIsUploadingTpl] = useState(false)
  const [isUpdatingTpl, setIsUpdatingTpl] = useState(false)

  const [templateAliases, setTemplateAliases] = useState<Record<string, string>>({})
  const [editingAliasName, setEditingAliasName] = useState<string | null>(null)
  const [aliasInputValue, setAliasInputValue] = useState('')
  const [activeTemplate, setActiveTemplate] = useState('')
  const [toastMsg, setToastMsg] = useState('')
  const [previewKey, setPreviewKey] = useState(() => Date.now())

  const [configOpen, setConfigOpen] = useState(false)
  const [configStatus, setConfigStatus] = useState<Record<string, string>>({})
  const [configInputs, setConfigInputs] = useState<Record<string, string>>({
    OPENAI_API_KEY: '', OPENAI_BASE_URL: '', SERPER_API_KEY: '',
    FEISHU_APP_ID: '', FEISHU_APP_SECRET: '', FEISHU_APP_TOKEN: '',
    OPENAI_MODEL: '', VISION_MODEL: '',
    FEISHU_TABLE_ID_JOBS: '', FEISHU_TABLE_ID_CONFIG: '', FEISHU_TABLE_ID_PROMPTS: '',
    FEISHU_TABLE_ID_RESUMES: '', FEISHU_TABLE_ID_PREFERENCES: ''
  })
  const [savingConfig, setSavingConfig] = useState(false)

  const fetchSysConfig = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/settings')
      const data = await res.json()
      setConfigStatus(data)
    } catch {}
  }

  const handleSaveConfig = async () => {
    const payload = Object.fromEntries(
      Object.entries(configInputs).filter(([, v]) => v.trim())
    )
    if (!Object.keys(payload).length) { showToast('⚠️ 没有需要更新的配置'); return }
    setSavingConfig(true)
    try {
      const res = await fetch('http://127.0.0.1:8000/api/settings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (res.ok && data.status === 'ok') {
        showToast('✅ ' + data.message)
        setConfigInputs({ OPENAI_API_KEY: '', OPENAI_BASE_URL: '', SERPER_API_KEY: '', FEISHU_APP_ID: '', FEISHU_APP_SECRET: '', FEISHU_APP_TOKEN: '', OPENAI_MODEL: '', VISION_MODEL: '', FEISHU_TABLE_ID_JOBS: '', FEISHU_TABLE_ID_CONFIG: '', FEISHU_TABLE_ID_PROMPTS: '', FEISHU_TABLE_ID_RESUMES: '', FEISHU_TABLE_ID_PREFERENCES: '' })
        fetchSysConfig()
      } else {
        alert('❌ 保存失败: ' + (data.detail || '未知错误'))
      }
    } catch { alert('❌ 网络错误，请确认后端服务已启动') }
    finally { setSavingConfig(false) }
  }

  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem('jobhunter_template_aliases')
        if (saved) setTemplateAliases(JSON.parse(saved))
      } catch {}
    }
  }, [])

  // 🌟 状态隔离：切换时只管右下角的结果，绝对不去碰左下角的 JD
  useEffect(() => {
    if (editingItem?.record_id) {
      setTestResult(resultCache[editingItem.record_id] || "")
      if (activeTab === 'prompt') {
        const name = editingItem.name;
        if (name.includes('评估') || name.includes('诊断')) {
          setTestMode('evaluate');
        } else if (name.includes('改写') || name.includes('定制')) {
          setTestMode('rewrite');
        } else if (name.includes('招呼') || name.includes('开场') || name.includes('沟通')) {
          setTestMode('greeting');
        }
      }
    } else {
      setTestResult("")
    }
  }, [editingItem?.record_id, activeTab])
  
  const handleFileImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    setIsParsing(true)
    const formData = new FormData()
    formData.append("file", file)

    try {
      // 调用我们在 main.py 里写的视觉解析接口
      const res = await fetch("http://127.0.0.1:8000/api/strategy/upload_resume_vision", {
        method: "POST",
        body: formData,
      })
      const data = await res.json()
      
      if (data.status === "success") {
        setEditingItem(prev => prev ? { ...prev, content: data.text } : null)
        alert("✅ 视觉解析成功！已按规范还原排版。")
      } else {
        alert("❌ 解析失败: " + data.detail)
      }
    } catch (err) {
      alert("❌ 网络错误，请确认后端服务已启动")
    } finally {
      setIsParsing(false)
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  const fetchConfig = async (currentEditingId?: string) => {
    setLoading(true)
    try {
      const res = await fetch("http://127.0.0.1:8000/api/strategy/config")
      const data = await res.json()
      if (data.status === "success") {
        const mappedResumes = data.resumes.map((r: any) => ({
          record_id: r.record_id, name: r.version_name, content: r.content, status: r.status
        }))
        const mappedPrompts = data.prompts.map((p: any) => ({
          record_id: p.record_id, name: p.strategy_name, content: p.content, status: p.status
        }))
        
        setResumes(mappedResumes)
        setPrompts(mappedPrompts)
        
        if (currentEditingId) {
          const target = [...mappedResumes, ...mappedPrompts].find(i => i.record_id === currentEditingId)
          if (target) setEditingItem(target)
        } else if (!editingItem) {
          if (activeTab === 'resume' && mappedResumes.length > 0) setEditingItem(mappedResumes[0])
          else if (activeTab === 'prompt' && mappedPrompts.length > 0) setEditingItem(mappedPrompts[0])
        }
      }
    } catch (err) {
      console.error("拉取配置失败:", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchConfig(); fetchSysConfig() }, [])

  useEffect(() => {
    if (activeTab === 'resume' && resumes.length > 0) setEditingItem(resumes[0])
    else if (activeTab === 'prompt' && prompts.length > 0) setEditingItem(prompts[0])
    else setEditingItem(null)
  }, [activeTab])

  const fetchTemplates = async () => {
    try {
      const t = Date.now()
      const [listRes, activeRes] = await Promise.all([
        fetch(`http://127.0.0.1:8000/api/templates?t=${t}`),
        fetch(`http://127.0.0.1:8000/api/templates/active?t=${t}`),
      ])
      const [listData, activeData] = await Promise.all([listRes.json(), activeRes.json()])
      if (listData.status === "success") {
        setTemplates(listData.templates)
        if (listData.templates.length > 0) {
          setSelectedTemplate((prev) => {
            if (prev) return listData.templates.find((t: TemplateItem) => t.name === prev.name) ?? listData.templates[0]
            return listData.templates[0]
          })
        } else {
          setSelectedTemplate(null)
        }
      }
      if (activeData.status === "success") {
        setActiveTemplate(activeData.active || "")
      }
    } catch (err) {
      console.error("获取模板列表失败:", err)
    }
  }

  useEffect(() => {
    if (activeTab === 'template') fetchTemplates()
  }, [activeTab])

  const handleTplUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setIsUploadingTpl(true)
    const formData = new FormData()
    formData.append("file", file)
    try {
      const res = await fetch("http://127.0.0.1:8000/api/templates", { method: "POST", body: formData })
      const data = await res.json()
      if (data.status === "success") {
        alert("✅ 模板上传成功！")
        setPreviewKey(Date.now())
        fetchTemplates()
      } else {
        alert("❌ 上传失败: " + (data.detail || "未知错误"))
      }
    } catch {
      alert("❌ 网络错误，请确认后端服务已启动")
    } finally {
      setIsUploadingTpl(false)
      if (tplInputRef.current) tplInputRef.current.value = ""
    }
  }

  const handleSetDefault = async (name: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/templates/${encodeURIComponent(name)}/default`, { method: "PUT" })
      const data = await res.json()
      if (data.status === "success") fetchTemplates()
      else alert("❌ 设置失败: " + (data.detail || "未知错误"))
    } catch {
      alert("❌ 网络错误")
    }
  }

  const handleDeleteTpl = async (name: string) => {
    if (!window.confirm(`确定要删除模板「${name}」吗？此操作不可恢复。`)) return
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/templates/${encodeURIComponent(name)}`, { method: "DELETE" })
      const data = await res.json()
      if (data.status === "success") { setSelectedTemplate(null); fetchTemplates() }
      else alert("❌ 删除失败: " + (data.detail || "未知错误"))
    } catch {
      alert("❌ 网络错误")
    }
  }

  const getDisplayName = (filename: string) =>
    templateAliases[filename] || filename.replace(/\.docx$/i, '')

  const saveAlias = (filename: string, alias: string) => {
    const trimmed = alias.trim()
    const updated = { ...templateAliases }
    if (trimmed) {
      updated[filename] = trimmed
    } else {
      delete updated[filename]
    }
    setTemplateAliases(updated)
    localStorage.setItem('jobhunter_template_aliases', JSON.stringify(updated))
    setEditingAliasName(null)
  }

  const showToast = (msg: string) => {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(''), 2800)
  }

  const handleSetActive = async (name: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/templates/active/${encodeURIComponent(name)}`, { method: 'POST' })
      const data = await res.json()
      if (data.status === 'success') {
        setActiveTemplate(name)
        showToast(`✅ 已切换生效模板：${getDisplayName(name)}`)
      } else {
        alert('❌ 切换失败: ' + (data.detail || '未知错误'))
      }
    } catch {
      alert('❌ 网络错误')
    }
  }

  const handleDownloadTpl = (name: string) => {
    window.location.href = `http://127.0.0.1:8000/api/templates/download/${encodeURIComponent(name)}`
  }

  const handleUpdateTpl = async (e: React.ChangeEvent<HTMLInputElement>, targetName: string) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.docx')) {
      alert('❌ 仅支持 .docx 格式文件')
      if (tplUpdateRef.current) tplUpdateRef.current.value = ''
      return
    }
    setIsUpdatingTpl(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/templates/${encodeURIComponent(targetName)}`, {
        method: 'PUT',
        body: formData,
      })
      const data = await res.json()
      if (data.status === 'success') {
        alert(`✅ 模板「${targetName}」已更新！检测到 ${data.variables?.length ?? 0} 个变量。`)
        setPreviewKey(Date.now())
        fetchTemplates()
      } else {
        alert('❌ 更新失败: ' + (data.detail || '未知错误'))
      }
    } catch {
      alert('❌ 网络错误，请确认后端服务已启动')
    } finally {
      setIsUpdatingTpl(false)
      if (tplUpdateRef.current) tplUpdateRef.current.value = ''
    }
  }

  const handleToggleResumeStatus = async (e: React.MouseEvent, item: StrategyItem) => {
    e.stopPropagation()
    if (!item.record_id || togglingResumeId) return
    setTogglingResumeId(item.record_id)
    try {
      const res = await fetch('http://127.0.0.1:8000/api/strategy/activate_resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ record_id: item.record_id })
      })
      const data = await res.json()
      if (res.ok && data.status === 'success') {
        await fetchConfig(editingItem?.record_id)
        showToast('✅ 已切换生效底稿')
      } else {
        alert('❌ 切换失败: ' + (data.detail || '未知错误'))
      }
    } catch (err) {
      alert('❌ 网络错误，请确认后端服务已启动')
    } finally {
      setTogglingResumeId(null)
    }
  }

  const handleCreateNew = () => {
    setEditingItem({
      name: activeTab === 'resume' ? '新建简历版本' : '新建Prompt策略',
      content: '',
      status: '停用'
    })
  }

  const handleSave = async () => {
    if (!editingItem) return
    if (!editingItem.name.trim()) return alert("名称不能为空！")
    
    setSaving(true)
    const payload = {
      table_type: activeTab,
      record_id: editingItem.record_id,
      fields: activeTab === 'resume' 
        ? { "简历版本": editingItem.name, "简历内容": editingItem.content, "当前状态": editingItem.status }
        : { "策略名称": editingItem.name, "Prompt内容": editingItem.content, "当前状态": editingItem.status }
    }

    try {
      const res = await fetch("http://127.0.0.1:8000/api/strategy/save", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (data.status === "success") {
        alert("✅ 保存飞书成功！")
        const newRecordId = data.record_id || editingItem.record_id
        setEditingItem(prev => prev ? { ...prev, record_id: newRecordId } : null)
        fetchConfig(newRecordId)
      } else {
        alert("❌ 保存失败: " + data.detail)
      }
    } catch (err) {
      alert("❌ 网络请求失败")
    } finally {
      setSaving(false)
    }
  }

  // 🌟 修复 2：“乐观更新” (Optimistic UI) 实现秒删体验
  const handleDelete = async (e: React.MouseEvent, item: StrategyItem) => {
    e.stopPropagation() 
    if (!item.record_id) return 
    
    if (!window.confirm(`⚠️ 危险操作：\n确定要永久删除「${item.name || '未命名'}」吗？\n此操作将同步删除飞书数据且不可恢复！`)) {
      return
    }

    // ⚡️ 动作 1：不等服务器，前端立刻把数据从列表里“假装”干掉（0延迟）
    if (activeTab === 'resume') {
      setResumes(prev => prev.filter(r => r.record_id !== item.record_id))
    } else {
      setPrompts(prev => prev.filter(p => p.record_id !== item.record_id))
    }

    // ⚡️ 动作 2：如果正在编辑这个项，立刻清空右侧面板
    if (editingItem?.record_id === item.record_id) {
      setEditingItem(null)
    }

    // ⚡️ 动作 3：后台默默去发请求给飞书
    try {
      const res = await fetch("http://127.0.0.1:8000/api/strategy/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          table_type: activeTab,
          record_id: item.record_id
        })
      })
      const data = await res.json()
      if (!res.ok || data.status !== "success") {
        // ⚡️ 动作 4 (兜底)：万一服务器挂了或飞书拒绝，抛出错误，并重新拉取数据恢复原状
        alert(`❌ 后台删除失败，数据将恢复: ${data.detail || '未知错误'}`)
        fetchConfig()
      }
    } catch (err) {
      alert(`❌ 网络请求异常，数据将恢复: ${String(err)}`)
      fetchConfig()
    }
  }

  const handleRunTest = async () => {
    if (!testJd.trim()) return alert("请输入用于测试的岗位 JD！")
    if (!editingItem?.content.trim()) return alert("Prompt 不能为空！")
    
    setIsTesting(true)
    setTestResult(">> 正在与 AI 建立连接，请稍候...")
    
    try {
      const res = await fetch("http://127.0.0.1:8000/api/strategy/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt_content: editingItem.content,
          jd_text: testJd,
          test_mode: testMode 
        })
      })
      const data = await res.json()
      if (res.ok && data.status === "success") {
        setTestResult(data.result)
        if (editingItem.record_id) {
          setResultCache(prev => ({ ...prev, [editingItem.record_id!]: data.result }))
        }
      } else {
        const errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail, null, 2);
        setTestResult(`❌ 测试运行失败:\n${errorDetail}`)
      }
    } catch (err) {
      setTestResult(`❌ 网络请求失败: ${String(err)}`)
    } finally {
      setIsTesting(false)
    }
  }

  const renderEvaluateResult = (jsonStr: string) => {
    try {
      let cleanStr = jsonStr;
      if (cleanStr.includes('{')) {
         cleanStr = cleanStr.substring(cleanStr.indexOf('{'), cleanStr.lastIndexOf('}') + 1);
      }
      const data = JSON.parse(cleanStr);
      const sections = [
        { title: "综合得分", content: `背景: ${data.bg_score || 0} | 技能: ${data.skill_score || 0} | 经验: ${data.exp_score || 0} | 总分: ${data.total_score || 0}` },
        { title: "技能要求", content: Array.isArray(data.extracted_skills) ? data.extracted_skills.join(", ") : data.extracted_skills },
        { title: "理想画像与能力信号", content: data.dream_picture },
        { title: "核心能力词典", content: data.ats_ability_analysis },
        { title: "高杠杆匹配点", content: data.strong_fit_assessment },
        { title: "致命硬伤与毒点", content: data.risk_red_flags },
        { title: "破局行动计划", content: data.deep_action_plan }
      ];
      
      return (
        <div className="w-full bg-white">
          {sections.map((s, i) => (
            <div key={i} className="border-b border-gray-100 last:border-0">
              <div className="py-3 px-5">
                <div className="text-[13px] font-bold text-gray-800 mb-1.5 flex items-center justify-between">
                   {s.title}
                </div>
                <div className="text-[13px] text-gray-600 leading-relaxed whitespace-pre-wrap">
                  {s.content || '暂无数据'}
                </div>
              </div>
            </div>
          ))}
        </div>
      );
    } catch(e) {
      return <div className="p-5 text-red-500 text-xs font-mono whitespace-pre-wrap">JSON解析失败，原始输出：<br/><br/>{jsonStr}</div>
    }
  }

  const configFields = [
    { key: 'OPENAI_API_KEY',    label: 'OpenAI API Key',    type: 'password' },
    { key: 'OPENAI_BASE_URL',   label: 'Base URL',          type: 'text'     },
    { key: 'SERPER_API_KEY',    label: 'Serper API Key',    type: 'password' },
    { key: 'FEISHU_APP_ID',     label: '飞书 App ID',        type: 'password' },
    { key: 'FEISHU_APP_SECRET', label: '飞书 App Secret',    type: 'password' },
    { key: 'FEISHU_APP_TOKEN',  label: '飞书 App Token',     type: 'password' },
  ]
  const modelFields = [
    { key: 'OPENAI_MODEL',  label: '推理模型 (OPENAI_MODEL)',  placeholder: 'deepseek-v3.1' },
    { key: 'VISION_MODEL',  label: '视觉模型 (VISION_MODEL)',  placeholder: 'qwen-vl-max'   },
  ]
  const tableIdFields = [
    { key: 'FEISHU_TABLE_ID_JOBS',        label: '岗位总表 (JOBS)',       placeholder: 'tblnHFxM'     },
    { key: 'FEISHU_TABLE_ID_CONFIG',      label: '搜索配置 (CONFIG)',     placeholder: 'tbl2fgL'      },
    { key: 'FEISHU_TABLE_ID_PROMPTS',     label: '策略库 (PROMPTS)',      placeholder: 'tbl2jP9Bq3c'  },
    { key: 'FEISHU_TABLE_ID_RESUMES',     label: '简历库 (RESUMES)',      placeholder: 'tblXbdNHn'    },
    { key: 'FEISHU_TABLE_ID_PREFERENCES', label: '偏好表 (PREFERENCES)', placeholder: 'tbltLDLR'     },
  ]

  const renderList = (items: StrategyItem[]) => {
    const isResumeTab = activeTab === 'resume'
    return items.map((item, idx) => {
      const isActive = item.status === '启用' || item.status === '启用中'
      const isStopped = item.status === '已停用' || item.status === '停用' || !isActive
      const isToggling = togglingResumeId === item.record_id
      return (
        <div
          key={item.record_id || idx}
          onClick={() => setEditingItem(item)}
          className={`p-4 border-b cursor-pointer transition-all duration-200 hover:bg-gray-50 flex items-center justify-between group
            ${editingItem?.record_id === item.record_id ? 'bg-blue-50 border-l-4 border-l-blue-600' : 'border-l-4 border-l-transparent'}
          `}
        >
          <div className="flex-1 min-w-0 pr-3">
            <div className="font-medium text-gray-800 truncate">{item.name || '未命名'}</div>
            <div className="text-xs text-gray-400 mt-1 truncate">{item.content ? item.content.substring(0, 20) + '...' : '暂无内容'}</div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {isActive
              ? <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-100 text-green-700 whitespace-nowrap">• 当前生效中</span>
              : <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-500 whitespace-nowrap">已停用</span>
            }
            {isResumeTab && isStopped && (
              <button
                onClick={(e) => handleToggleResumeStatus(e, item)}
                disabled={!!togglingResumeId}
                className="text-[10px] px-1.5 py-0.5 rounded font-medium border transition-all whitespace-nowrap opacity-0 group-hover:opacity-100
                  text-green-700 bg-green-50 border-green-200 hover:bg-green-100 disabled:opacity-40 disabled:cursor-not-allowed"
                title="设为唯一启用"
              >
                {isToggling ? '切换中...' : '设为启用'}
              </button>
            )}
            <button
              onClick={(e) => handleDelete(e, item)}
              className="text-gray-300 hover:text-red-500 hover:bg-red-50 p-1.5 rounded-md transition-all opacity-0 group-hover:opacity-100"
              title="永久删除"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      )
    })
  }

  return (
    <div className="flex flex-col h-full w-full">

      {/* === 🔐 系统底层配置卡片 === */}
      <div className="shrink-0 bg-white border-b border-gray-200 shadow-sm">
        <button
          onClick={() => setConfigOpen(v => !v)}
          className="w-full flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 bg-indigo-600 rounded-md flex items-center justify-center shrink-0">
              <Settings size={13} className="text-white" />
            </div>
            <span className="text-sm font-semibold text-gray-700">系统底层配置</span>
            <div className="flex items-center gap-1 ml-1">
              {configFields.map(f => (
                <span key={f.key} title={f.label}
                  className={`w-1.5 h-1.5 rounded-full transition-colors ${
                    configStatus[f.key] ? 'bg-emerald-400' : 'bg-gray-200'
                  }`}
                />
              ))}
            </div>
          </div>
          {configOpen
            ? <ChevronUp size={15} className="text-gray-400" />
            : <ChevronDown size={15} className="text-gray-400" />}
        </button>

        {configOpen && (
          <div className="px-5 pb-5 border-t border-gray-100 bg-white">
            <div className="grid grid-cols-3 gap-x-4 gap-y-4 mt-4">
              {configFields.map(f => (
                <div key={f.key}>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <label className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">{f.label}</label>
                    {configStatus[f.key]
                      ? <span className="text-[10px] font-mono bg-emerald-50 text-emerald-600 border border-emerald-200 px-1.5 py-0.5 rounded truncate max-w-[90px]">{configStatus[f.key]}</span>
                      : <span className="text-[10px] bg-gray-50 text-gray-400 border border-gray-200 px-1.5 py-0.5 rounded">未配置</span>}
                  </div>
                  <input
                    type={f.type}
                    value={configInputs[f.key] || ''}
                    onChange={e => setConfigInputs(prev => ({ ...prev, [f.key]: e.target.value }))}
                    placeholder={f.type === 'text' ? 'https://api.openai.com/v1' : '粘贴新密鑰以覆盖...'}
                    className="w-full text-xs px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-gray-50 placeholder-gray-300 transition-all"
                  />
                </div>
              ))}
            </div>

            {/* 🤖 模型名称配置 (2列) */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-4 mt-4">
              {modelFields.map(f => (
                <div key={f.key}>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <label className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide">{f.label}</label>
                    {configStatus[f.key] && (
                      <span className="text-[10px] font-mono bg-emerald-50 text-emerald-600 border border-emerald-200 px-1.5 py-0.5 rounded truncate max-w-[90px]">{configStatus[f.key]}</span>
                    )}
                  </div>
                  <input
                    type="text"
                    value={configInputs[f.key] || ''}
                    onChange={e => setConfigInputs(prev => ({ ...prev, [f.key]: e.target.value }))}
                    placeholder={f.placeholder}
                    className="w-full text-xs px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-gray-50 placeholder-gray-300 transition-all"
                  />
                </div>
              ))}
            </div>

            {/* 🔗 Feishu 表 ID 区域 */}
            <div className="mt-4 rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 mb-3">Feishu Bitable · Table IDs</p>
              <div className="grid grid-cols-3 gap-x-3 gap-y-3">
                {tableIdFields.map(f => (
                  <div key={f.key}>
                    <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide block mb-1">{f.label}</label>
                    <input
                      type="text"
                      value={configInputs[f.key] || ''}
                      onChange={e => setConfigInputs(prev => ({ ...prev, [f.key]: e.target.value }))}
                      placeholder={f.placeholder}
                      className="w-full text-[10px] font-mono px-2.5 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent bg-white placeholder-slate-300 transition-all"
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-4 flex justify-end">
              <button
                onClick={handleSaveConfig}
                disabled={savingConfig}
                className="flex items-center gap-2 px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-[13px] font-semibold rounded-lg transition-colors disabled:opacity-50 shadow-sm"
              >
                {savingConfig ? <RefreshCw size={13} className="animate-spin" /> : <Save size={13} />}
                {savingConfig ? '保存中...' : '保存配置'}
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-1 min-h-0 w-full bg-white overflow-hidden">
      
      <div className="w-80 border-r flex flex-col bg-white shadow-sm z-10 shrink-0">
        <div className="p-4 border-b bg-gray-50 flex justify-between items-center">
          <h2 className="text-lg font-bold text-gray-800">策略大盘</h2>
          <button onClick={() => fetchConfig()} className="p-2 text-gray-500 hover:text-blue-600 rounded-full hover:bg-blue-50">
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
        <div className="flex p-2 gap-1 bg-gray-50 border-b">
          <button onClick={() => setActiveTab('resume')} className={`flex-1 py-1.5 text-xs font-medium rounded-md flex items-center justify-center gap-1.5 ${activeTab === 'resume' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:bg-gray-200'}`}><FileText size={14} /> 简历库</button>
          <button onClick={() => setActiveTab('prompt')} className={`flex-1 py-1.5 text-xs font-medium rounded-md flex items-center justify-center gap-1.5 ${activeTab === 'prompt' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:bg-gray-200'}`}><MessageSquare size={14} /> Prompt库</button>
          <button onClick={() => setActiveTab('template')} className={`flex-1 py-1.5 text-xs font-medium rounded-md flex items-center justify-center gap-1.5 ${activeTab === 'template' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:bg-gray-200'}`}><Layout size={14} /> 模板仓库</button>
        </div>
        <div className="flex-1 overflow-y-auto min-h-0">
          {activeTab === 'resume' ? renderList(resumes) : activeTab === 'prompt' ? renderList(prompts) : (
            templates.length === 0 ? (
              <div className="p-6 text-center text-gray-400 text-sm">暂无模板，请先上传</div>
            ) : (
              templates.map((tpl) => {
                const isActive = tpl.name === activeTemplate
                return (
                  <div
                    key={tpl.name}
                    onClick={() => setSelectedTemplate(tpl)}
                    className={`px-4 py-3 border-b cursor-pointer transition-all duration-200 hover:bg-gray-50 flex items-center justify-between group
                      ${selectedTemplate?.name === tpl.name ? 'bg-blue-50 border-l-4 border-l-blue-600' : 'border-l-4 border-l-transparent'}
                    `}
                  >
                    <div className="flex-1 min-w-0 pr-2">
                      {editingAliasName === tpl.name ? (
                        <input
                          autoFocus
                          className="w-full text-sm font-bold text-gray-800 bg-white border border-blue-400 rounded px-1.5 py-0.5 outline-none focus:ring-1 focus:ring-blue-400"
                          value={aliasInputValue}
                          placeholder="输入自定义名称..."
                          onChange={(e) => setAliasInputValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') { e.preventDefault(); saveAlias(tpl.name, aliasInputValue) }
                            if (e.key === 'Escape') setEditingAliasName(null)
                          }}
                          onBlur={() => saveAlias(tpl.name, aliasInputValue)}
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <div className="flex items-center gap-1.5 min-w-0">
                          <div className="font-bold text-gray-800 truncate text-sm leading-snug">{getDisplayName(tpl.name)}</div>
                          {isActive && (
                            <span className="shrink-0 text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full font-semibold whitespace-nowrap">当前启用</span>
                          )}
                        </div>
                      )}
                      <div className="text-xs text-gray-400 mt-0.5 truncate">{tpl.name}</div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      {!isActive && (
                        <button
                          title="设为启用"
                          onClick={(e) => { e.stopPropagation(); handleSetActive(tpl.name) }}
                          className="text-[10px] px-1.5 py-0.5 rounded font-medium transition-all opacity-0 group-hover:opacity-100 whitespace-nowrap text-gray-400 hover:text-green-700 hover:bg-green-50 border border-transparent hover:border-green-200"
                        >
                          启用
                        </button>
                      )}
                      <button
                        title="自定义别名"
                        onClick={(e) => {
                          e.stopPropagation()
                          setAliasInputValue(templateAliases[tpl.name] || '')
                          setEditingAliasName(tpl.name)
                        }}
                        className="p-1 rounded text-gray-300 hover:text-blue-500 hover:bg-blue-50 transition-all opacity-0 group-hover:opacity-100"
                      >
                        <Edit2 size={12} />
                      </button>
                    </div>
                  </div>
                )
              })
            )
          )}
          <div className="p-4">
            {activeTab === 'template' ? (
              <>
                <input type="file" accept=".docx" ref={tplInputRef} className="hidden" onChange={handleTplUpload} />
                <button
                  onClick={() => tplInputRef.current?.click()}
                  disabled={isUploadingTpl}
                  className="w-full py-3 border-2 border-dashed border-gray-300 rounded-lg text-gray-500 font-medium flex items-center justify-center gap-2 hover:border-blue-500 hover:text-blue-600 disabled:opacity-50"
                >
                  {isUploadingTpl ? <RefreshCw size={18} className="animate-spin" /> : <Upload size={18} />}
                  {isUploadingTpl ? '上传中...' : '上传新模板 (.docx)'}
                </button>
              </>
            ) : (
              <button onClick={handleCreateNew} className="w-full py-3 border-2 border-dashed border-gray-300 rounded-lg text-gray-500 font-medium flex items-center justify-center gap-2 hover:border-blue-500 hover:text-blue-600">
                <Plus size={18} /> 新建{activeTab === 'resume' ? '简历' : 'Prompt'}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="flex-1 flex flex-col bg-gray-50/50 h-full overflow-hidden min-w-0">
        {activeTab === 'template' ? (
          selectedTemplate ? (
            <>
              <div className="h-14 px-5 border-b bg-white flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3 min-w-0">
                  <FileText size={18} className="text-blue-600 shrink-0" />
                  <span className="font-bold text-gray-800 truncate">{selectedTemplate.name}</span>
                  {selectedTemplate.is_default && (
                    <span className="text-[11px] bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium whitespace-nowrap">当前默认</span>
                  )}
                </div>
                <div className="flex items-center gap-1.5 shrink-0 flex-wrap justify-end">
                  {!selectedTemplate.is_default && (
                    <button
                      onClick={() => handleSetDefault(selectedTemplate.name)}
                      className="flex items-center gap-1 px-2 py-1.5 bg-blue-50 border border-blue-200 text-blue-700 rounded text-[11px] font-medium hover:bg-blue-100"
                    >
                      <CheckCircle size={13} /> 设为默认
                    </button>
                  )}
                  <button
                    onClick={() => handleDownloadTpl(selectedTemplate.name)}
                    className="flex items-center gap-1 px-2 py-1.5 bg-slate-50 border border-slate-200 text-slate-700 rounded text-[11px] font-medium hover:bg-slate-100"
                  >
                    <Download size={13} /> 下载
                  </button>
                  <button
                    onClick={() => tplUpdateRef.current?.click()}
                    disabled={isUpdatingTpl}
                    className="flex items-center gap-1 px-2 py-1.5 bg-amber-50 border border-amber-200 text-amber-700 rounded text-[11px] font-medium hover:bg-amber-100 disabled:opacity-50"
                  >
                    {isUpdatingTpl ? <RefreshCw size={13} className="animate-spin" /> : <Upload size={13} />}
                    {isUpdatingTpl ? '更新中...' : '更新模板'}
                  </button>
                  <button
                    onClick={() => handleDeleteTpl(selectedTemplate.name)}
                    className="flex items-center gap-1 px-2 py-1.5 bg-red-50 border border-red-200 text-red-600 rounded text-[11px] font-medium hover:bg-red-100"
                  >
                    <Trash2 size={13} /> 删除
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-gray-50/30">
                {/* 隐藏文件输入（更新模板） */}
                <input
                  type="file"
                  accept=".docx"
                  ref={tplUpdateRef}
                  className="hidden"
                  onChange={(e) => handleUpdateTpl(e, selectedTemplate.name)}
                />

                {/* 文件基本信息 */}
                <div className="flex items-center gap-4 p-4 bg-white rounded-xl border border-gray-100 shadow-sm">
                  <div className="w-12 h-14 bg-blue-50 border border-blue-200 rounded-lg flex flex-col items-center justify-center gap-1 shrink-0">
                    <FileText size={24} className="text-blue-400" />
                    <span className="text-[9px] font-mono text-blue-400">.docx</span>
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold text-gray-800 text-sm truncate">{selectedTemplate.name}</p>
                    <p className="text-xs text-gray-400 mt-0.5">大小：{(selectedTemplate.size / 1024).toFixed(1)} KB</p>
                    {selectedTemplate.is_default ? (
                      <span className="inline-block mt-1.5 text-[10px] bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">✅ 当前默认导出模板</span>
                    ) : (
                      <span className="inline-block mt-1.5 text-[10px] bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">可在导出时指定使用</span>
                    )}
                  </div>
                </div>

                {/* 变量扫描结果 */}
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-gray-700">已识别变量</h3>
                    <span className="text-xs text-gray-400">{selectedTemplate.variables?.length ?? 0} 个</span>
                  </div>

                  {!(selectedTemplate.variables ?? []).includes('sections') && (
                    <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700">
                      <span className="shrink-0">⚠️</span>
                      <span>未检测到核心变量 <code className="bg-amber-100 px-1 rounded font-mono">{'{'}{'{ sections }}'}</code>，模板可能无法正确渲染各模块内容。</span>
                    </div>
                  )}

                  {(selectedTemplate.variables ?? []).length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {(selectedTemplate.variables ?? []).map((v) => {
                        const isCore = ['name', 'contact', 'intention', 'sections'].includes(v)
                        return (
                          <span
                            key={v}
                            className={`inline-flex items-center text-[11px] font-mono px-2 py-0.5 rounded border ${
                              isCore
                                ? 'bg-blue-50 border-blue-200 text-blue-700 font-semibold'
                                : 'bg-gray-50 border-gray-200 text-gray-600'
                            }`}
                          >
                            {'{{ '}{v}{' }}'}
                          </span>
                        )
                      })}
                    </div>
                  ) : (
                    <p className="text-xs text-gray-400 italic">未检测到变量，请确认模板中包含正确的 {'{{ }}'} 标记</p>
                  )}
                </div>

                {/* 逻辑标签 */}
                {(selectedTemplate.tags ?? []).some(t => ['for', 'if', 'endfor', 'endif', 'else'].includes(t)) && (
                  <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 space-y-3">
                    <h3 className="text-sm font-bold text-gray-700">逻辑标签</h3>
                    <div className="flex flex-wrap gap-1.5">
                      {(selectedTemplate.tags ?? [])
                        .filter(t => ['for', 'if', 'endfor', 'endif', 'else', 'set'].includes(t))
                        .map((t) => (
                          <span key={t} className="text-[11px] font-mono px-2 py-0.5 rounded border bg-purple-50 border-purple-200 text-purple-600">
                            {'{% '}{t}{' %}'}
                          </span>
                        ))}
                    </div>
                  </div>
                )}

                {/* 模板截图预览 */}
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 space-y-3">
                  <h3 className="text-sm font-bold text-gray-700">模板预览</h3>
                  <TemplatePreviewImage name={selectedTemplate.name} cacheKey={previewKey} />
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
              <Layout size={64} className="mb-4 opacity-20" />
              <p>请在左侧选择一个模板，或点击“上传新模板”</p>
            </div>
          )
        ) : editingItem ? (
          <>
            <div className="h-14 px-5 border-b bg-white flex items-center justify-between shrink-0 gap-4">
              <input 
                type="text" 
                value={editingItem.name} 
                onChange={(e) => setEditingItem({...editingItem, name: e.target.value})} 
                placeholder="请输入名称..." 
                className="text-lg font-bold text-gray-800 bg-transparent border-none outline-none focus:ring-0 flex-1 min-w-0" 
              />
              
              <div className="flex items-center gap-2 shrink-0">
                <button onClick={() => setEditingItem({...editingItem, status: editingItem.status === '启用' ? '停用' : '启用'})} className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[12px] font-medium border transition-colors whitespace-nowrap ${editingItem.status === '启用' ? 'bg-green-50 border-green-200 text-green-700 hover:bg-green-100' : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'}`}>
                  {editingItem.status === '启用' ? <CheckCircle size={14} /> : <Circle size={14} />}
                  {editingItem.status === '启用' ? '当前生效中' : '点击设为启用'}
                </button>
                <button onClick={handleSave} disabled={saving} className="flex items-center gap-1.5 px-2.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-[12px] font-medium transition-colors disabled:opacity-50 whitespace-nowrap">
                  <Save size={14} /> {saving ? '保存中...' : '同步到飞书'}
                </button>
              </div>
            </div>

            <div className="flex-1 p-6 flex flex-col min-h-0">
              <div className="mb-3 flex flex-col gap-1.5 shrink-0">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-800 font-bold">
                    {activeTab === 'resume' ? '简历正文 (纯文本/Markdown 格式)' : 'Prompt 策略设定 (核心设定与打分规则)'}
                  </span>
                  
                  {/* 👇 新增：导入 PDF/Word 的按钮 */}
                  {activeTab === 'resume' && (
                    <div className="flex gap-2">
                      <input 
                        type="file" 
                        accept=".pdf,.docx" 
                        ref={fileInputRef} 
                        className="hidden"
                        onChange={handleFileImport} 
                      />
                      <button 
                        onClick={() => fileInputRef.current?.click()}
                        disabled={isParsing}
                        className="text-[11px] bg-slate-800 hover:bg-slate-700 text-white px-3 py-1.5 rounded flex items-center gap-1.5 transition-all shadow-sm disabled:opacity-50"
                      >
                        {isParsing ? <RefreshCw size={12} className="animate-spin" /> : "📎 视觉识别 PDF/Word"}
                      </button>
                    </div>
                  )}
                </div>

                {/* Prompt 库的提示 */}
                {activeTab === 'prompt' && (
                  <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded w-fit border border-amber-100">
                    ⚠️ 提示：JSON 格式约束已锁定在底层引擎中，此处仅需填写策略逻辑。
                  </span>
                )}
                
                {/* 简历库的专属格式提醒 */}
                {activeTab === 'resume' && (
                  <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded w-fit border border-blue-100">
                    💡 格式要求：请使用单个 # 加模块名作为大标题（例：#个人总结、#项目经历），正文直接换行。
                  </span>
                )}
              </div>
                
                <textarea 
                value={editingItem.content}
                onChange={(e) => setEditingItem({...editingItem, content: e.target.value})}
                /* 👇 新增：将简历的默认 placeholder 换成一个直观的格式模板 */
                placeholder={
                    activeTab === 'resume' 
                        ? "#个人信息\n姓名：张三 | 手机号：138xxxx\n求职意向：AI产品经理\n\n#个人总结\n近5年电商业务底盘...\n\n#专业技能\n##大模型生态与自动化\n- 精通 Prompt Engineering...\n\n#项目经历\n##项目名称：全自动岗位抓取...\n项目描述：独立开发..." 
                        : "你现在是一位拥有 10 年经验的资深 HR... 【重构原则】..."
                }
                className="flex-1 w-full p-5 border border-gray-200 rounded-xl shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none font-mono text-[13px] leading-relaxed bg-white"
            />
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
            {activeTab === 'resume' ? <FileText size={64} className="mb-4 opacity-20" /> : <MessageSquare size={64} className="mb-4 opacity-20" />}
            <p>请在左侧选择一个项目，或点击新建</p>
          </div>
        )}
      </div>

      {activeTab === 'prompt' && editingItem && (
        <div className="w-[450px] 2xl:w-[500px] border-l flex flex-col bg-slate-50 z-20 shrink-0 h-full overflow-hidden">
          
          <div className="h-14 bg-slate-800 text-white flex items-center justify-between px-4 shrink-0">
            <div className="flex flex-col gap-1">
              <span className="font-bold flex items-center gap-2 text-sm"><Play size={14} className="text-green-400" /> 策略沙盒 (Playground)</span>
              <select 
                value={testMode} 
                onChange={(e) => setTestMode(e.target.value as any)}
                className="bg-slate-700 text-[11px] text-slate-300 border-none rounded px-1 py-0.5 outline-none cursor-pointer hover:bg-slate-600 transition-colors max-w-[180px] truncate"
              >
                <option value="evaluate">模式: 深度评估 (JSON)</option>
                <option value="rewrite">模式: 简历改写 (JSON)</option>
                <option value="greeting">模式: 打招呼语 (纯文本)</option>
              </select>
            </div>

            <button 
              onClick={handleRunTest} 
              disabled={isTesting}
              className="flex items-center gap-2 bg-green-500 hover:bg-green-600 text-white px-3 py-1.5 rounded-md text-xs font-medium transition-colors disabled:opacity-50"
            >
              {isTesting ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} fill="currentColor" />}
              {isTesting ? '执行中...' : '测试打靶'}
            </button>
          </div>

          <div className="h-[35%] border-b border-slate-200 flex flex-col bg-white shrink-0">
            <div className="text-xs font-bold text-slate-600 p-2.5 bg-slate-50 border-b flex items-center gap-2 shrink-0">
              <span>🎯 目标岗位 JD (Target Input)</span>
            </div>
            <textarea 
              value={testJd}
              onChange={(e) => setTestJd(e.target.value)}
              placeholder="请粘贴你要测试的真实岗位 JD..."
              className="flex-1 w-full p-4 bg-transparent border-none focus:ring-0 resize-none text-[13px] leading-relaxed"
            />
          </div>

          <div className="flex-1 flex flex-col bg-white overflow-hidden min-h-0">
            <div className="text-xs font-bold text-slate-600 p-2.5 bg-slate-50 border-b border-slate-200 flex items-center gap-2 shrink-0">
              <Terminal size={14} />
              <span>大模型输出结果 (Output Panel)</span>
            </div>
            
            <div className="flex-1 overflow-y-auto min-h-0">
              {testResult ? (
                testMode === 'evaluate' ? renderEvaluateResult(testResult) : (
                  <div className="p-5 text-gray-800 font-mono text-[13px] leading-relaxed whitespace-pre-wrap break-words select-text">
                    {testResult}
                  </div>
                )
              ) : (
                <div className="p-5 text-slate-400 font-mono text-[13px] whitespace-pre-wrap select-text">
                  {`// 等待执行指令...\n// 1. 在上方输入岗位 JD\n// 2. 确认测试模式无误\n// 3. 点击右上角 [测试打靶]`}
                </div>
              )}
            </div>
          </div>
          
        </div>
      )}

      {toastMsg && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-5 py-2.5 bg-gray-800 text-white text-sm rounded-full shadow-xl whitespace-nowrap">
          {toastMsg}
        </div>
      )}
      </div>
    </div>
  )
}