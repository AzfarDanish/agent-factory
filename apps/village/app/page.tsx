'use client'

import { useEffect, useState, useRef } from 'react'
import VillageView from './tilemap/village-view'
import type { MapData } from './tilemap/types'
import { SpriteCharacter, getRandomHair } from '@/components/SpriteCharacter'

// ═══════════════════════════════════════════
// REGISTRY
// ═══════════════════════════════════════════

interface Build { id: string; label: string; role: string; col: number; row: number; tileW: number; tileH: number; cx: number; cy: number }

const B: Build[] = [
  { id: 'house-A', label: 'Gatehouse',  role: 'Intake',       col: 22, row: 8,  tileW: 80,  tileH: 112, cx: 0, cy: 0 },
  { id: 'house-B', label: 'Scriptorium',role: 'Prompt Craft',  col: 50, row: 8,  tileW: 80,  tileH: 112, cx: 0, cy: 0 },
  { id: 'church',  label: 'Sanctum',    role: 'Gather & Brief',col: 38, row: 18, tileW: 128, tileH: 112, cx: 0, cy: 0 },
  { id: 'house-C', label: 'Artisan Hall',role:'Image Generation',col: 55,row: 22, tileW: 128, tileH: 112, cx: 0, cy: 0 },
  { id: 'house-D', label: 'Bindery',    role: 'Assembly',     col: 22, row: 20, tileW: 80,  tileH: 112, cx: 0, cy: 0 },
  { id: 'house-E', label: 'Archive',    role: 'Output',       col: 48, row: 34, tileW: 80,  tileH: 112, cx: 0, cy: 0 },
  { id: 'house-F', label: 'Workshop',   role: 'Quality Check',col: 18, row: 32, tileW: 80,  tileH: 112, cx: 0, cy: 0 },
  { id: 'pit',     label: 'The Pit',    role: 'Error',        col: 36, row: 41, tileW: 32,  tileH: 48,  cx: 0, cy: 0 },
]
for (const b of B) { b.cx = b.col * 16 + b.tileW / 2; b.cy = b.row * 16 + b.tileH / 2 }
const BLDG = new Map(B.map(b => [b.id, b]))

// ═══════════════════════════════════════════
// AGENTS  (home building, name, role)
// ═══════════════════════════════════════════

interface A { id: string; name: string; home: string; role: string; hair: H; workBldg: string }

const AGENT_DEFS: A[] = [
  { id: 'a1', name: 'Luna', home: 'house-A', role: 'Intake',     hair: 'shorthair', workBldg: 'house-A' },
  { id: 'a2', name: 'Kael', home: 'house-B', role: 'Prompt Craft',hair: 'shorthair', workBldg: 'church' },
  { id: 'a3', name: 'Nova', home: 'house-C', role: 'Image Gen',   hair: 'shorthair', workBldg: 'house-C' },
  { id: 'a4', name: 'Orin', home: 'house-D', role: 'Assembly',    hair: 'shorthair', workBldg: 'house-E' },
]
type H = 'shorthair' | 'bowlhair' | 'curlyhair' | 'longhair' | 'mophair' | 'spikeyhair'
for (const a of AGENT_DEFS) { a.hair = getRandomHair() as H }

// ═══════════════════════════════════════════
// STATE MACHINE
// ═══════════════════════════════════════════

type AgentStatus = 'idle' | 'walk' | 'work' | 'celebrate' | 'fail'
type ManagerMsg = { from: string; text: string; ts: number }

interface AgentState {
  id: string; name: string; fromBldg: string; toBldg: string
  p: number; status: AgentStatus; role: string; hair: H; home: string
}

const BRIDGE = process.env.NEXT_PUBLIC_BRIDGE_URL || 'http://localhost:3002'

function pos(bldg: string) {
  const b = BLDG.get(bldg)!
  return { x: b.cx, y: b.cy }
}

export default function Home() {
  const [data, setData] = useState<MapData | null>(null)
  const [agents, setAgents] = useState<AgentState[]>([])
  const [msgs, setMsgs] = useState<ManagerMsg[]>([])
  const [queues, setQueues] = useState<Record<string, number>>({})
  const [done, setDone] = useState(0)
  const [prompt, setPrompt] = useState('')
  const [ageGroup, setAgeGroup] = useState('child')
  const [style, setStyle] = useState('cartoon')
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [showForm, setShowForm] = useState(true)
  const [expandedBubble, setExpandedBubble] = useState<string | null>(null)
  const [taskActive, setTaskActive] = useState(false)
  const [currentStage, setCurrentStage] = useState(0) // 0=idle, 1=intake, 2=reasoning, 3=image, 4=assembly, 5=done
  const idxRef = useRef(0)
  const stageRef = useRef(0)
  stageRef.current = currentStage

  // Init agents at home
  useEffect(() => {
    const initial = AGENT_DEFS.map(a => ({
      id: a.id, name: a.name, fromBldg: a.home, toBldg: a.home,
      p: 0, status: 'idle' as AgentStatus, role: a.role, hair: a.hair, home: a.home,
    }))
    setAgents(initial)
  }, [])

  // Load tile data
  useEffect(() => { fetch('/tilemap-village.json').then(r => r.json()).then(setData) }, [])

  // Animation loop
  useEffect(() => {
    const tick = setInterval(() => {
      setAgents(prev => {
        let c = false
        const n = prev.map(a => {
          if (a.status !== 'walk') return a
          const np = a.p + 0.03
          if (np >= 1) { c = true; return { ...a, p: 1, status: 'work' as const } }
          c = true
          return { ...a, p: np }
        })
        return c ? n : prev
      })
    }, 80)
    return () => clearInterval(tick)
  }, [])

  // Poll bridge
  useEffect(() => {
    if (!data) return
    const poll = async () => {
      try {
        const [s, e] = await Promise.all([
          fetch(`${BRIDGE}/state`).then(r => r.json()),
          fetch(`${BRIDGE}/events?after=${idxRef.current}`).then(r => r.json()),
        ])
        setQueues(s.queue_depths || {})
        if (e.count > 0) { idxRef.current += e.count; processEvents(e.events) }
      } catch {}
    }
    poll(); const t = setInterval(poll, 1000); return () => clearInterval(t)
  }, [data])

  function processEvents(events: any[]) {
    for (const ev of events) {
      const stage = ev.stage
      const promptText = (ev.prompt || 'page').slice(0, 25)

      if (stage === 'reasoning' && !taskActive) {
        setTaskActive(true)
        setCurrentStage(0)
        addMsg('Hermes', `📋 New request: "${promptText}" — gather at Sanctum!`)
        // Stage 0: all agents walk to church
        moveAllTo('church')
      }
      if (stage === 'generating' && currentStage < 2) advancePipeline()
      if (stage === 'completed' && currentStage < 3) advancePipeline()
      if (stage === 'done' && currentStage < 4) advancePipeline()
    }
  }

  function advancePipeline() {
    const next = stageRef.current + 1
    setCurrentStage(next)
    const agent = AGENT_DEFS[next - 1]
    if (agent) {
      agentWalksToWork(agent.id)
    }
  }

  function moveAllTo(bldgId: string) {
    setAgents(prev => prev.map(a => {
      // If already at church, stay
      if (a.toBldg === bldgId && a.p >= 1) return a
      return { ...a, fromBldg: a.toBldg, toBldg: bldgId, p: 0, status: 'walk' as const }
    }))
  }

  function agentWalksToWork(agentId: string) {
    const def = AGENT_DEFS.find(a => a.id === agentId)!
    addMsg(def.name, startingMsg(def.role))
    setAgents(prev => prev.map(a =>
      a.id === agentId
        ? { ...a, fromBldg: a.toBldg, toBldg: def.workBldg, p: 0, status: 'walk' as const }
        : a
    ))
    // When agent arrives at work building, schedule return
    setTimeout(() => {
      addMsg(def.name, doneMsg(def.role))
      // Return to church, then trigger next stage
      setAgents(prev => prev.map(a =>
        a.id === agentId
          ? { ...a, fromBldg: def.workBldg, toBldg: 'church', p: 0, status: 'walk' as const }
          : a
      ))
      // After returning, advance pipeline
      setTimeout(() => advancePipeline(), 4000)
    }, 5000)
  }

  function addMsg(from: string, text: string) {
    setMsgs(prev => [...prev.slice(-8), { from, text, ts: Date.now() }])
  }

  function startingMsg(role: string): string {
    const m: Record<string, string> = {
      'Intake': 'Request logged. Over to Kael for prompt crafting.',
      'Prompt Craft': 'Prompt refined for coloring page. Nova, generate it!',
      'Image Gen': 'Coloring page generated! Orin, assemble the output.',
      'Assembly': 'PDF assembled. Stored in output/cartoon/2026-07-21/',
    }
    return m[role] || `Working on ${role.toLowerCase()}...`
  }

  function doneMsg(role: string): string {
    const m: Record<string, string> = {
      'Intake': `Intake done. Returning to Sanctum.`,
      'Prompt Craft': `Crafted the perfect prompt. Back to Sanctum.`,
      'Image Gen': `Artwork complete! Heading back.`,
      'Assembly': `All stored. Mission complete!`,
    }
    return m[role] || `Done. Returning.`
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
          const f = BLDG.get(a.fromBldg)!
          const t = BLDG.get(a.toBldg)!
          const x = f.cx + (t.cx - f.cx) * a.p
          const y = f.cy + (t.cy - f.cy) * a.p
          const anim = a.status === 'work' ? 'work' : a.status === 'celebrate' ? 'celebrate' : a.status === 'fail' ? 'fail' : a.status === 'idle' ? 'idle' : 'walk'
          const latestMsg = msgs.filter(m => m.from === a.name).slice(-1)[0]
          const isExpanded = expandedBubble === a.id

          return (
            <div key={a.id} className="absolute z-20 flex flex-col items-center" style={{ left: x - 48, top: y - 64 }}>
              {/* Chat bubble */}
              {latestMsg && (
                <div className="relative mb-1.5 cursor-pointer select-none" style={{ maxWidth: 180 }} onClick={() => setExpandedBubble(isExpanded ? null : a.id)}>
                  <div className="bg-gray-900/95 backdrop-blur-md border border-gray-600/60 rounded-xl px-3 py-1.5 text-center shadow-xl">
                    <div className="text-[9px] text-gray-400 font-semibold uppercase tracking-wider mb-0.5">{a.name}</div>
                    <div className="text-[10px] text-white leading-snug">{latestMsg.text}</div>
                    {isExpanded && (
                      <div className="mt-1.5 pt-1.5 border-t border-gray-700/40 text-[8px] text-gray-500">
                        Role: {a.role} | Status: {a.status}
                      </div>
                    )}
                  </div>
                  <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-gray-900/95 border-r border-b border-gray-600/60 rotate-45" />
                </div>
              )}

              {/* Character */}
              <div className="relative">
                <div className="w-8 h-2 rounded-full bg-black/30 mx-auto mb-[-4px]" />
                <SpriteCharacter anim={anim} hair={a.hair} />
              </div>

              {/* Name label — always visible */}
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
        {Object.entries(queues).map(([q, d]) => (
          <div key={q} className="flex justify-between mb-1"><span className="text-gray-300">{q}</span><span className={`font-mono ${(d as number) > 0 ? 'text-blue-300' : 'text-gray-500'}`}>{(d as number) > 0 ? `${d}` : '—'}</span></div>
        ))}
        <div className="border-t border-gray-700/50 mt-1.5 pt-1.5 flex justify-between"><span className="text-gray-400">Done</span><span className="font-mono text-green-300">{done}</span></div>
        {msgs.slice(-1).map((m, i) => (
          <div key={i} className="mt-2 pt-1.5 border-t border-gray-700/50 text-[9px]">
            <span className="text-gray-500">{m.from}:</span> <span className="text-gray-300">{m.text.slice(0, 40)}</span>
          </div>
        ))}
      </div>
    </VillageView>
  )
}
