'use client'

import { useEffect, useState, useRef } from 'react'
import VillageView from './tilemap/village-view'
import type { MapData } from './tilemap/types'
import { SpriteCharacter, getRandomHair } from '@/components/SpriteCharacter'

// ═══════════════════════════════════════════
// BUILDING DEFINITIONS
// ═══════════════════════════════════════════

interface Build { id: string; label: string; role: string; col: number; row: number; tileW: number; tileH: number; cx: number; cy: number }

const B: Build[] = [
  { id: 'house-A', label: 'Gatehouse',  role: 'Intake',         col: 22, row: 8,  tileW: 80,  tileH: 112, cx: 0, cy: 0 },
  { id: 'house-B', label: 'Scriptorium',role: 'Prompt Craft',   col: 50, row: 8,  tileW: 80,  tileH: 112, cx: 0, cy: 0 },
  { id: 'church',  label: 'Sanctum',    role: 'Gather & Brief', col: 38, row: 18, tileW: 128, tileH: 112, cx: 0, cy: 0 },
  { id: 'house-C', label: 'Artisan Hall',role:'Image Generation',col: 55,row: 22, tileW: 128, tileH: 112, cx: 0, cy: 0 },
  { id: 'house-D', label: 'Bindery',    role: 'Assembly',       col: 22, row: 20, tileW: 80,  tileH: 112, cx: 0, cy: 0 },
  { id: 'house-E', label: 'Archive',    role: 'Output',         col: 48, row: 34, tileW: 80,  tileH: 112, cx: 0, cy: 0 },
  { id: 'house-F', label: 'Workshop',   role: 'Quality Check',  col: 18, row: 32, tileW: 80,  tileH: 112, cx: 0, cy: 0 },
  { id: 'pit',     label: 'The Pit',    role: 'Error',          col: 36, row: 41, tileW: 32,  tileH: 48,  cx: 0, cy: 0 },
]
for (const b of B) { b.cx = b.col * 16 + b.tileW / 2; b.cy = b.row * 16 + b.tileH / 2 }
const BLDG = new Map(B.map(b => [b.id, b]))

// ═══════════════════════════════════════════
// PATH SYSTEM  — direct point-to-point
// ═══════════════════════════════════════════

type Point = { x: number; y: number }
function getPath(fromId: string, toId: string): Point[] {
  if (fromId === toId) return [pos(fromId)]
  return [pos(fromId), pos(toId)]
}

// ═══════════════════════════════════════════
// AGENT FACTORY  —  spawned from bridge events
// ═══════════════════════════════════════════

const HAIR_TYPES = ['shorthair', 'bowlhair', 'curlyhair', 'longhair', 'mophair', 'spikeyhair'] as const
type H = typeof HAIR_TYPES[number]

// Mapping: workflow stage → target building for that agent task
const STAGE_TO_BUILDING: Record<string, string> = {
  // Coloring pipeline
  'intake':        'house-A',
  'prompt_craft':  'house-B',
  'gather_brief':  'church',
  'image_gen':     'house-C',
  'assembly':      'house-D',
  'output':        'house-E',
  'quality_check': 'house-F',
}

// Names pool for auto-spawned agents
const AGENT_NAMES = ['Luna', 'Kael', 'Nova', 'Orin', 'Sage', 'Faye', 'Thorn', 'Zale', 'Iris', 'Rune', 'Vale', 'Lyra']
let nameIdx = 0

// ═══════════════════════════════════════════
// STATE TYPES
// ═══════════════════════════════════════════

type AgentStatus = 'idle' | 'walk' | 'work' | 'celebrate' | 'fail'
type ManagerMsg = { from: string; text: string; ts: number }

interface AgentState {
  id: string; name: string; trace_id: string
  path: Point[]; pathIdx: number; p: number
  status: AgentStatus; hair: H
  curBldg: string; homeBldg: string; workBldg: string
  workflow: string
}

interface ErrorDisplay {
  type: string; message: string; details: string
  agent: string; stage: string; timestamp: string; trace_id: string
}

const BRIDGE = process.env.NEXT_PUBLIC_BRIDGE_URL || 'http://localhost:3001'

function pos(bldg: string) {
  const b = BLDG.get(bldg)!
  return { x: b.cx, y: b.cy }
}

function randomHair(): H { return HAIR_TYPES[Math.floor(Math.random() * HAIR_TYPES.length)] }

// ═══════════════════════════════════════════
// HOME COMPONENT
// ═══════════════════════════════════════════

export default function Home() {
  const [data, setData] = useState<MapData | null>(null)
  const [agents, setAgents] = useState<AgentState[]>([])
  const [msgs, setMsgs] = useState<ManagerMsg[]>([])
  const [queues, setQueues] = useState<Record<string, number>>({})
  const [errors, setErrors] = useState<ErrorDisplay[]>([])
  const [prompt, setPrompt] = useState('')
  const [ageGroup, setAgeGroup] = useState('child')
  const [style, setStyle] = useState('cartoon')
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [showForm, setShowForm] = useState(true)
  const [expandedBubble, setExpandedBubble] = useState<string | null>(null)
  const [taskActive, setTaskActive] = useState(false)
  const [currentStage, setCurrentStage] = useState(0)
  const [showErrors, setShowErrors] = useState(false)

  const idxRef = useRef(0)
  const errorIdxRef = useRef(0)
  const agentsRef = useRef<AgentState[]>([])
  const pipelineRef = useRef({
    phase: 'idle' as 'idle' | 'gathering' | 'active' | 'complete',
    agentIdx: -1,
    currentTraceId: '' as string,
    subPhase: '' as 'walk_to_work' | 'working' | 'walk_to_church' | '',
    workEndTime: 0,
    taskActive: false,
  })

  // ── Persistent named agents (spawned on first event) ──
  const namedAgentsRef = useRef<{ name: string; hair: H; homeBldg: string; workBldg: string }[]>([])

  function spawnNamedAgent(trace_id: string, stage: string, workflow: string): string {
    const workBldg = STAGE_TO_BUILDING[stage] || 'church'
    const homeBldg = 'house-A'

    const name = AGENT_NAMES[nameIdx % AGENT_NAMES.length]; nameIdx++
    const hair = randomHair()
    namedAgentsRef.current.push({ name, hair, homeBldg, workBldg })

    const agent: AgentState = {
      id: `job-${trace_id.slice(0, 6)}`,
      name, trace_id,
      path: [pos(homeBldg)], pathIdx: 0, p: 0,
      status: 'idle', hair,
      curBldg: homeBldg, homeBldg, workBldg,
      workflow,
    }
    setAgents(prev => [...prev, agent])
    setCurrentStage(0)
    return name
  }

  function getAgentByTrace(trace_id: string): AgentState | undefined {
    return agentsRef.current.find(a => a.trace_id === trace_id)
  }

  // Load tile data
  useEffect(() => { fetch('/tilemap-village.json').then(r => r.json()).then(setData) }, [])

  // Keep ref in sync
  useEffect(() => { agentsRef.current = agents }, [agents])

  // ── Animation loop  —  advances walking agents
  useEffect(() => {
    const tick = setInterval(() => {
      setAgents(prev => {
        let changed = false
        const next = prev.map(a => {
          if (a.status !== 'walk' || a.path.length < 2) return a
          const np = a.p + 0.03
          if (np >= 1) {
            changed = true
            return { ...a, p: 1, status: 'idle' as const, path: [], pathIdx: 0 }
          }
          changed = true
          return { ...a, p: np }
        })
        return changed ? next : prev
      })
    }, 80)
    return () => clearInterval(tick)
  }, [])

  // ── Bridge + errors poll  (every 1s)
  useEffect(() => {
    if (!data) return
    let init = true
    const poll = async () => {
      try {
        const [s, e, err_resp] = await Promise.all([
          fetch(`${BRIDGE}/state`).then(r => r.json()),
          fetch(`${BRIDGE}/events?after=${idxRef.current}`).then(r => r.json()),
          fetch(`${BRIDGE}/errors`).then(r => r.json()),
        ])
        setQueues(s.queue_depths || {})
        setErrors(err_resp.errors || [])
        if (init) {
          idxRef.current = s.event_count || 0
          init = false
        } else if (e.count > 0) {
          idxRef.current += e.count
          processEvents(e.events)
        }
      } catch {
        // bridge not running — silent
      }
    }
    poll(); const t = setInterval(poll, 1000); return () => clearInterval(t)
  }, [data])

  // ── Pipeline driver  —  watches agent positions and drives sequence
  useEffect(() => {
    if (!taskActive) return
    const t = setInterval(() => {
      const p = pipelineRef.current
      if (!p.taskActive) return

      // GATHERING: wait until every agent is idle at church
      if (p.phase === 'gathering') {
        const agents = agentsRef.current
        // Check agents for the current trace
        const traceAgents = agents.filter(a => a.trace_id === p.currentTraceId)
        if (traceAgents.length > 0 && traceAgents.every(a => a.status === 'idle' && a.curBldg === 'church')) {
          p.phase = 'active'
          p.agentIdx = 0
          setCurrentStage(1)
          addMsg('Hermes', 'Agent at the Sanctum!')
          startAgent(0)
        }
        return
      }

      if (p.phase !== 'active' || !p.subPhase) return

      const traceAgents = agentsRef.current.filter(a => a.trace_id === p.currentTraceId)
      const a = traceAgents[p.agentIdx]
      if (!a) return

      // Arrived at work
      if (p.subPhase === 'walk_to_work' && a.status === 'idle' && a.curBldg === a.workBldg) {
        p.subPhase = 'working'
        p.workEndTime = Date.now() + 3000
        setAgents(prev => prev.map(x => x.id === a.id ? { ...x, status: 'work' as const } : x))
        return
      }

      // Work timer expired
      if (p.subPhase === 'working' && Date.now() >= p.workEndTime) {
        addMsg(a.name, `${a.name} completed task. Returning.`)
        if (a.workBldg === 'church') {
          advanceToNext(p.agentIdx)
          return
        }
        p.subPhase = 'walk_to_church'
        setAgents(prev => prev.map(x =>
          x.id === a.id
            ? { ...x, path: getPath(a.workBldg, 'church'), pathIdx: 0, p: 0, status: 'walk' as const, curBldg: 'church' }
            : x
        ))
        return
      }

      // Returned to church
      if (p.subPhase === 'walk_to_church' && a.status === 'idle' && a.curBldg === 'church') {
        advanceToNext(p.agentIdx)
        return
      }
    }, 200)
    return () => clearInterval(t)
  }, [taskActive])

  // ── Idle patrol
  useEffect(() => {
    const t = setInterval(() => {
      const currentAgents = agentsRef.current
      setAgents(prev => prev.map(a => {
        if (a.status !== 'idle') return a
        const ref = currentAgents.find(x => x.id === a.id)
        if (ref && ref.status !== 'idle') return a
        const b = BLDG.get(a.curBldg)
        if (!b) return a
        const angle = Math.random() * Math.PI * 2
        const dist = 30 + Math.random() * 20
        return {
          ...a,
          path: [pos(a.curBldg), { x: b.cx + Math.cos(angle) * dist, y: b.cy + Math.sin(angle) * dist }],
          pathIdx: 0, p: 0,
          status: 'walk' as const,
        }
      }))
    }, 3000)
    return () => clearInterval(t)
  }, [])

  // ── Pipeline actions ──

  function processEvents(events: any[]) {
    for (const ev of events) {
      const stage = ev.stage
      const workflow = ev.workflow || 'coloring'
      const trace_id = ev.trace_id
      const promptText = (ev.prompt || 'page').slice(0, 25)

      // New request: spawn agent and start gathering
      if (stage === 'reasoning' || stage === 'research' || stage === 'outline') {
        const p = pipelineRef.current
        if (p.taskActive) {
          // Already processing — queue this trace for next round
          addMsg('Hermes', `📋 Queued: "${promptText}" (${workflow})`)
          continue
        }
        p.taskActive = true
        p.currentTraceId = trace_id
        p.phase = 'gathering'

        // Spawn agent for this workflow + stage
        spawnNamedAgent(trace_id, promptText, workflow)
        setTaskActive(true)
        addMsg('Hermes', `📋 New ${workflow}: "${promptText}" — agent gathering at Sanctum!`)
        gatherAgents()
      }

      // Stage completed: advance agent
      if (stage === 'generating' || stage === 'synthesize' || stage === 'write') {
        const a = getAgentByTrace(trace_id)
        if (a) {
          setAgents(prev => prev.map(x =>
            x.id === a.id ? { ...x, status: 'work' as const } : x
          ))
        }
      }

      // Pipeline completed
      if (stage === 'done' || stage === 'deliver') {
        const a = getAgentByTrace(trace_id)
        if (a) {
          setAgents(prev => prev.map(x =>
            x.id === a.id ? { ...x, status: 'celebrate' as const } : x
          ))
          setTimeout(() => {
            setAgents(prev => prev.filter(x => x.id !== a.id))
          }, 4000)
        }
      }

      // Pipeline failed
      if (stage === 'failed') {
        addMsg('Hermes', `❌ Pipeline failed: "${promptText}"`)
        const a = getAgentByTrace(trace_id)
        if (a) {
          setAgents(prev => prev.map(x =>
            x.id === a.id ? { ...x, status: 'fail' as const } : x
          ))
        }
      }
    }
  }

  function gatherAgents() {
    setAgents(prev => prev.map(a => {
      if (a.curBldg === 'church' && a.status === 'idle') return a
      return {
        ...a, path: getPath(a.curBldg, 'church'),
        pathIdx: 0, p: 0, status: 'walk' as const, curBldg: 'church',
      }
    }))
  }

  function startAgent(idx: number) {
    const p = pipelineRef.current
    const traceAgents = agentsRef.current.filter(a => a.trace_id === p.currentTraceId)
    const a = traceAgents[idx]
    if (!a) return

    if (a.workBldg === 'church') {
      p.subPhase = 'working'
      p.workEndTime = Date.now() + 2000
      setAgents(prev => prev.map(x => x.id === a.id ? { ...x, status: 'work' as const } : x))
    } else {
      p.subPhase = 'walk_to_work'
      setAgents(prev => prev.map(x =>
        x.id === a.id
          ? { ...x, path: getPath('church', a.workBldg), pathIdx: 0, p: 0, status: 'walk' as const, curBldg: a.workBldg }
          : x
      ))
    }
    addMsg(a.name, `Moving to work...`)
  }

  function advanceToNext(idx: number) {
    const p = pipelineRef.current
    const nextIdx = idx + 1
    p.agentIdx = nextIdx
    p.subPhase = ''
    setCurrentStage(nextIdx + 1)

    const traceAgents = agentsRef.current.filter(a => a.trace_id === p.currentTraceId)
    if (nextIdx >= traceAgents.length) {
      p.phase = 'complete'
      p.taskActive = false
      setTaskActive(false)
      setCurrentStage(traceAgents.length)
      addMsg('Hermes', '🎉 Task complete!')
    } else {
      startAgent(nextIdx)
    }
  }

  function addMsg(from: string, text: string) {
    setMsgs(prev => [...prev.slice(-8), { from, text, ts: Date.now() }])
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!prompt.trim() || submitting) return
    setSubmitting(true); setFeedback(''); setShowForm(false)

    try {
      const res = await fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt.trim(), age_group: ageGroup, style }),
      })
      const j = await res.json()
      if (j.success) {
        setFeedback('Task submitted! Agents gathering...')
        fetch('/api/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run_pipeline: true }),
        })
        setPrompt('')
        setTimeout(() => setShowForm(true), 3000)
      } else { setFeedback(`Error: ${j.error}`) }
    } catch { setFeedback('Connection failed') }
    setSubmitting(false)
  }

  if (!data) return <div className="h-screen w-screen bg-black" />

  return (
    <VillageView data={data}>
      {/* ── AGENTS ── */}
      <div className="absolute inset-0 z-20 pointer-events-none">
        {agents.map(a => {
          const pos_ = (() => {
            if (a.path.length < 2) {
              const b = BLDG.get(a.curBldg)!
              return { x: b.cx, y: b.cy }
            }
            const idx = Math.min(a.pathIdx, a.path.length - 2)
            const s = a.path[idx]
            const e = a.path[idx + 1]
            return { x: s.x + (e.x - s.x) * a.p, y: s.y + (e.y - s.y) * a.p }
          })()
          const anim = a.status === 'work' ? 'work' : a.status === 'celebrate' ? 'celebrate' : a.status === 'fail' ? 'fail' : a.status === 'idle' ? 'idle' : 'walk'
          const latestMsg = msgs.filter(m => m.from === a.name).slice(-1)[0]
          const isExpanded = expandedBubble === a.id

          return (
            <div key={a.id} className="absolute z-20 flex flex-col items-center" style={{ left: pos_.x - 48, top: pos_.y - 64 }}>
              {latestMsg && (
                <div className="relative mb-1.5 cursor-pointer select-none" style={{ maxWidth: 180 }} onClick={() => setExpandedBubble(isExpanded ? null : a.id)}>
                  <div className="bg-gray-900/95 backdrop-blur-md border border-gray-600/60 rounded-xl px-3 py-1.5 text-center shadow-xl">
                    <div className="text-[9px] text-gray-400 font-semibold uppercase tracking-wider mb-0.5">{a.name}</div>
                    <div className="text-[10px] text-white leading-snug">{latestMsg.text}</div>
                    {isExpanded && (
                      <div className="mt-1.5 pt-1.5 border-t border-gray-700/40 text-[8px] text-gray-500">
                        Workflow: {a.workflow} | Status: {a.status}
                      </div>
                    )}
                  </div>
                  <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-gray-900/95 border-r border-b border-gray-600/60 rotate-45" />
                </div>
              )}
              <div className="relative">
                <div className="w-8 h-2 rounded-full bg-black/30 mx-auto mb-[-4px]" />
                <SpriteCharacter anim={anim} hair={a.hair} />
              </div>
              <div className="mt-1 px-2 py-0.5 bg-black text-white text-[9px] font-bold rounded-full border border-white/20 shadow-md whitespace-nowrap">
                {a.name}
              </div>
            </div>
          )
        })}
      </div>

      {/* ── BUILDING LABELS ── */}
      <div className="absolute inset-0 z-10 pointer-events-none">
        {B.map(b => (
          <div key={b.id} className="absolute flex flex-col items-center" style={{ left: b.cx - 40, top: b.cy + 24 }}>
            <span className="px-2 py-0.5 bg-black text-white text-[8px] font-bold rounded-full shadow-lg whitespace-nowrap border border-white/10">
              {b.role}
            </span>
          </div>
        ))}
      </div>

      {/* ── SUBMIT FORM ── */}
      {showForm && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-30 bg-gray-900/90 backdrop-blur-md border border-gray-700 rounded-2xl shadow-2xl p-4 w-[500px] max-w-[90vw]">
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div className="flex items-center gap-2 text-xs text-gray-400 font-semibold uppercase tracking-wider"><span>🎨</span><span>Request a coloring page</span></div>
            <textarea value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Describe the coloring page..."
              className="w-full bg-gray-800/70 border border-gray-600 rounded-xl px-3 py-2 text-sm text-white placeholder-gray-500 resize-none focus:outline-none focus:border-blue-500" rows={2} maxLength={200} />
            <div className="flex gap-2">
              <select value={ageGroup} onChange={e => setAgeGroup(e.target.value)} className="flex-1 bg-gray-800/70 border border-gray-600 rounded-lg px-2 py-1.5 text-xs text-white">
                <option value="toddler">Toddler</option><option value="child">Child</option><option value="teen">Teen</option><option value="adult">Adult</option>
              </select>
              <select value={style} onChange={e => setStyle(e.target.value)} className="flex-1 bg-gray-800/70 border border-gray-600 rounded-lg px-2 py-1.5 text-xs text-white">
                <option value="simple">Simple</option><option value="cartoon">Cartoon</option><option value="detailed">Detailed</option><option value="mandala">Mandala</option><option value="realistic">Realistic</option>
              </select>
              <button type="submit" disabled={submitting || !prompt.trim()} className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-xs font-semibold rounded-lg transition-colors">
                {submitting ? '...' : 'Send'}
              </button>
            </div>
            {feedback && <div className="text-xs text-center text-gray-400">{feedback}</div>}
          </form>
        </div>
      )}
      {!showForm && <button onClick={() => setShowForm(true)} className="absolute bottom-6 left-1/2 -translate-x-1/2 z-30 px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-full shadow-lg transition-colors">+ New Request</button>}

      {/* ── STATUS PANEL ── */}
      <div className="absolute top-4 right-4 z-30 bg-gray-900/80 backdrop-blur-sm rounded-xl border border-gray-700 p-3 min-w-[150px] text-white text-xs shadow-xl">
        <div className="font-bold uppercase tracking-wider text-gray-400 mb-2">Pipeline</div>
        {Object.entries(queues).filter(([, d]) => (d as number) > 0).slice(0, 8).map(([q, d]) => (
          <div key={q} className="flex justify-between mb-1"><span className="text-gray-300 text-[10px]">{q}</span><span className="font-mono text-blue-300">{d}</span></div>
        ))}
        {Object.entries(queues).filter(([, d]) => (d as number) > 0).length === 0 && (
          <div className="text-[9px] text-gray-500 italic">All queues empty</div>
        )}
        <div className="border-t border-gray-700/50 mt-1.5 pt-1.5 flex justify-between">
          <span className="text-gray-400">Active</span>
          <span className="font-mono text-green-300">{agents.length} agents</span>
        </div>
        {msgs.slice(-1).map((m, i) => (
          <div key={i} className="mt-2 pt-1.5 border-t border-gray-700/50 text-[9px]">
            <span className="text-gray-500">{m.from}:</span> <span className="text-gray-300">{m.text.slice(0, 40)}</span>
          </div>
        ))}
      </div>

      {/* ── ERROR PANEL ── */}
      <div className="absolute bottom-4 left-4 z-30">
        <button
          onClick={() => setShowErrors(!showErrors)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors shadow-lg border ${
            errors.length > 0
              ? 'bg-red-900/80 border-red-700 text-red-200 hover:bg-red-800/80'
              : 'bg-gray-900/80 border-gray-700 text-gray-400 hover:bg-gray-800/80'
          }`}
        >
          <span className="text-base">⚠</span>
          <span>Errors</span>
          {errors.length > 0 && (
            <span className="ml-0.5 px-1.5 py-0.5 bg-red-600 text-white text-[9px] font-bold rounded-full min-w-[18px] text-center">
              {errors.length > 99 ? '99+' : errors.length}
            </span>
          )}
        </button>
        {showErrors && (
          <div className="mt-2 w-[420px] max-w-[90vw] max-h-[300px] bg-gray-950/95 backdrop-blur-md border border-gray-700/80 rounded-xl shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 border-b border-gray-800">
              <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider">Error Log</span>
              <div className="flex items-center gap-2">
                <span className="text-[9px] text-gray-500">{errors.length} total</span>
                <button onClick={() => setErrors([])} className="text-[9px] text-gray-600 hover:text-gray-400 transition-colors">Clear</button>
              </div>
            </div>
            <div className="overflow-y-auto max-h-[240px]">
              {errors.length === 0 ? (
                <div className="px-3 py-4 text-center text-[11px] text-gray-600">No errors recorded</div>
              ) : (
                [...errors].reverse().slice(0, 50).map((err, i) => {
                  const isCritical = err.type === 'pipeline_error' || err.type === 'file_error'
                  const isWarning = err.type === 'json_decode_error' || err.type === 'processing_error'
                  return (
                    <div key={i} className={`px-3 py-2 border-b border-gray-800/50 last:border-0 ${isCritical ? 'bg-red-950/30' : isWarning ? 'bg-yellow-950/20' : ''}`}>
                      <div className="flex items-start gap-2">
                        <span className="mt-0.5 text-[10px]">{isCritical ? '🔴' : isWarning ? '🟡' : '🔵'}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[10px] font-semibold truncate text-gray-300">{err.message}</span>
                            <span className="text-[8px] text-gray-600 whitespace-nowrap font-mono">{err.timestamp?.split('T')[1]?.replace('Z', '') || ''}</span>
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[8px] text-gray-500 bg-gray-800/60 px-1.5 py-0.5 rounded-full">{err.type}</span>
                            {err.stage && <span className="text-[8px] text-gray-600">{err.stage}</span>}
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        )}
      </div>
    </VillageView>
  )
}
