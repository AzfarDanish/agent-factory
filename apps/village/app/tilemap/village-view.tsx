'use client'

import { useRef, useEffect, useState } from 'react'
import { TILE_MAP } from './tile-data'
import type { MapData } from './types'

const CELL = 16

function tileUrl(id: string, day: boolean) {
  return `/tiles/${id} - ${day ? 'DAY' : 'NIGHT'}.png`.replace(/ /g, '%20')
}

export default function VillageView({ data, children }: { data: MapData; children?: React.ReactNode }) {
  const wrap = useRef<HTMLDivElement>(null)
  const [fit, setFit] = useState({ zoom: 1, panX: 0, panY: 0 })

  useEffect(() => {
    const el = wrap.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect()
      const zoomX = r.width / (data.cols * CELL)
      const zoomY = r.height / (data.rows * CELL)
      const zoom = Math.min(zoomX, zoomY)
      setFit({
        zoom,
        panX: (r.width - data.cols * CELL * zoom) / 2,
        panY: (r.height - data.rows * CELL * zoom) / 2,
      })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [data])

  const { zoom, panX, panY } = fit
  const cellPx = CELL * zoom

  return (
    <div ref={wrap} className="h-screen w-screen overflow-hidden bg-black">
      <div
        style={{
          width: data.cols * cellPx,
          height: data.rows * cellPx,
          transform: `translate(${panX}px, ${panY}px)`,
          position: 'relative',
          backgroundImage: [
            'linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px)',
            'linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)',
          ].join(', '),
          backgroundSize: `${cellPx}px ${cellPx}px`,
        }}
      >
        {data.tiles
          .filter(t => t.layer === 'ground')
          .map((t, i) => {
            const def = TILE_MAP[t.id]
            if (!def) return null
            return (
              <img
                key={`g-${i}`}
                src={tileUrl(t.id, true)}
                alt=""
                draggable={false}
                style={{
                  position: 'absolute',
                  left: t.col * cellPx,
                  top: t.row * cellPx,
                  width: def.width * zoom,
                  height: def.height * zoom,
                  imageRendering: 'pixelated',
                }}
              />
            )
          })}
        {data.tiles
          .filter(t => t.layer === 'objects')
          .map((t, i) => {
            const def = TILE_MAP[t.id]
            if (!def) return null
            return (
              <img
                key={`o-${i}`}
                src={tileUrl(t.id, true)}
                alt=""
                draggable={false}
                style={{
                  position: 'absolute',
                  left: t.col * cellPx,
                  top: t.row * cellPx,
                  width: def.width * zoom,
                  height: def.height * zoom,
                  imageRendering: 'pixelated',
                }}
              />
            )
          })}
        {children}
      </div>
    </div>
  )
}
