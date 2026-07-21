import { writeFileSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const COLS = 90
const ROWS = 50

const tileGrid = {}
function setTile(layer, col, row, id) {
  if (!tileGrid[layer]) tileGrid[layer] = {}
  if (!tileGrid[layer][row]) tileGrid[layer][row] = {}
  tileGrid[layer][row][col] = id
}

function pick(arr, col, row, offset = 0) {
  return arr[(col * 7 + row * 13 + offset) % arr.length]
}

function chance(col, row, seed, pct) {
  return ((col * 31 + row * 17 + seed * 41) % 100) < pct * 100
}

function pathRect(c1, c2, r1, r2) {
  for (let r = r1; r <= r2; r++)
    for (let c = c1; c <= c2; c++)
      setTile('ground', c, r, 'GROUND TILE')
}

const G = 'GRASS TILE'
const P = 'GROUND TILE'
const W = 'WATER TILE'

for (let r = 0; r < ROWS; r++)
  for (let c = 0; c < COLS; c++)
    setTile('ground', c, r, G)

// ---- S-CURVE RIVER ----
function isRiver(c, r) {
  if (c <= 20) return r >= 43 && r <= 46
  if (c <= 50) return r >= 44 && r <= 47
  return r >= 43 && r <= 46
}

for (let r = 0; r < ROWS; r++)
  for (let c = 0; c < COLS; c++)
    if (isRiver(c, r))
      setTile('ground', c, r, W)

for (let r = 0; r < ROWS; r++)
  for (let c = 0; c < COLS; c++)
    if (isRiver(c, r)) {
      if (!isRiver(c, r - 1)) setTile('ground', c, r - 1, P)
      if (!isRiver(c, r + 1)) setTile('ground', c, r + 1, P)
    }

// ---- ROADS ----
pathRect(0, COLS - 1, 16, 17)
pathRect(28, 50, 18, 19)

pathRect(23, 24, 9, 15)
pathRect(51, 52, 9, 15)
pathRect(18, 19, 25, 31)
pathRect(49, 50, 28, 33)
pathRect(61, 62, 28, 31)

pathRect(42, 47, 20, 41)

// ---- TERRAIN SET 4 — River Banks ----
const terrain4Positions = [
  [10, 39], [28, 40], [42, 40], [68, 39],
]
for (const [c, r] of terrain4Positions)
  setTile('ground', c, r, 'TERRAIN SET 4')

// ---- TERRAIN SET 4 CURVES — Shoreline Corners ----
const terrain4cPositions = [
  [20, 42], [50, 42],
]
for (const [c, r] of terrain4cPositions)
  setTile('ground', c, r, 'TERRAIN SET 4 CURVES')

// ---- TERRAIN SET 1 — Path Edge Transitions ----
const terrain1Positions = [
  [5, 14], [10, 14], [15, 14], [20, 14],
  [52, 14], [58, 14], [65, 14], [72, 14], [80, 14],
  [8, 17], [22, 17], [52, 17], [62, 17], [75, 17],
  [30, 19], [35, 19], [45, 19],
]
for (const [c, r] of terrain1Positions)
  setTile('ground', c, r, 'TERRAIN SET 1')

// ---- TERRAIN SET 3 CURVES — Curved Path Corners ----
const terrain3cPositions = [
  [22, 14], [50, 14], [17, 16], [50, 16],
]
for (const [c, r] of terrain3cPositions)
  setTile('ground', c, r, 'TERRAIN SET 3 CURVES')

// ---- TERRAIN SET 5 — Small Clearings ----
setTile('ground', 72, 10, 'TERRAIN SET 5')
setTile('ground', 8, 34, 'TERRAIN SET 5')

// ---- TERRAIN SET 2 — Forest Clearing with Puddle ----
setTile('ground', 75, 28, 'TERRAIN SET 2')

// ---- TERRAIN SET 3 — Multi-layer Path Feature ----
setTile('ground', 6, 12, 'TERRAIN SET 3')

// ---- WATER DETAILS ----
const wd = ['WATER DETAIL 1', 'WATER DETAIL 2', 'WATER DETAIL 3', 'WATER DETAIL 4', 'WATER DETAIL 5']
for (let r = 0; r < ROWS; r++)
  for (let c = 0; c < COLS; c++)
    if (isRiver(c, r) && chance(c, r, 1, 0.18))
      setTile('ground', c, r, pick(wd, c, r, 0))

// ---- GRASS DETAILS ----
const gd = ['GRASS DETAIL 1', 'GRASS DETAIL 2', 'GRASS DETAIL 3', 'GRASS DETAIL 4', 'GRASS DETAIL 5', 'GRASS DETAIL 6']
for (let r = 0; r < ROWS; r++)
  for (let c = 0; c < COLS; c++) {
    const cur = tileGrid['ground']?.[r]?.[c]
    if (cur !== G && cur?.startsWith?.('GRASS')) continue
    if (cur !== G) continue
    if (chance(c, r, 2, 0.035))
      setTile('ground', c, r, pick(gd, c, r, 1))
  }

// ---- GROUND DETAILS ----
const pd = ['GROUND DETAIL 1', 'GROUND DETAIL 2', 'GROUND DETAIL 3', 'GROUND DETAIL 4', 'GROUND DETAIL 5']
for (let r = 0; r < ROWS; r++)
  for (let c = 0; c < COLS; c++) {
    const cur = tileGrid['ground']?.[r]?.[c]
    if (cur !== P) continue
    if (chance(c, r, 3, 0.055))
      setTile('ground', c, r, pick(pd, c, r, 2))
  }

// ---- OBJECTS ----
setTile('objects', 38, 18, 'CHURCH')
setTile('objects', 55, 22, 'HOUSE 2')
setTile('objects', 22, 8, 'HOUSE 1')
setTile('objects', 50, 8, 'HOUSE 1')
setTile('objects', 22, 20, 'HOUSE 1')
setTile('objects', 18, 32, 'HOUSE 1')
setTile('objects', 48, 34, 'HOUSE 1')
setTile('objects', 60, 32, 'HOUSE 1')

function fencePerimeter(c1, c2, r1, r2, openSide, openMid, type = 'FENCE 1') {
  for (let c = c1; c <= c2; c++) {
    if (openSide === 'top' && c >= openMid - 1 && c <= openMid + 1) continue
    setTile('objects', c, r1, type)
  }
  for (let c = c1; c <= c2; c++) {
    if (openSide === 'bottom' && c >= openMid - 1 && c <= openMid + 1) continue
    setTile('objects', c, r2, type)
  }
  for (let r = r1 + 1; r < r2; r++) {
    if (openSide === 'left' && r >= openMid - 1 && r <= openMid + 1) continue
    setTile('objects', c1, r, type)
  }
  for (let r = r1 + 1; r < r2; r++) {
    if (openSide === 'right' && r >= openMid - 1 && r <= openMid + 1) continue
    setTile('objects', c2, r, type)
  }
}

fencePerimeter(35, 48, 15, 28, 'bottom', 42)
fencePerimeter(52, 65, 19, 31, 'bottom', 59)
fencePerimeter(19, 29, 5, 17, 'bottom', 24)
fencePerimeter(47, 57, 5, 17, 'bottom', 52)
fencePerimeter(19, 29, 17, 29, 'top', 24, 'FENCE 2')
fencePerimeter(15, 25, 29, 41, 'top', 20, 'FENCE 2')
fencePerimeter(45, 55, 31, 43, 'top', 50, 'FENCE 2')
fencePerimeter(57, 67, 29, 41, 'top', 62, 'FENCE 2')

setTile('objects', 42, 42, 'BRIDGE')
setTile('objects', 12, 44, 'STAIRS')
setTile('objects', 70, 44, 'STAIRS')
setTile('objects', 36, 41, 'PIT')

const treeIds = ['TREE 1', 'TREE 2', 'TREE 3']
const treePositions = [
  [5, 2], [14, 3], [34, 2], [44, 3], [68, 2], [82, 3],
  [6, 48], [22, 47], [54, 48], [76, 47], [84, 48],
  [14, 18], [30, 13], [54, 15], [30, 37], [56, 37],
  [4, 40], [60, 40],
]
for (const [c, r] of treePositions)
  setTile('objects', c, r, pick(treeIds, c, r, 4))

const tiles = []
for (const [layer, rows] of Object.entries(tileGrid))
  for (const [row, cols] of Object.entries(rows))
    for (const [col, id] of Object.entries(cols))
      tiles.push({ id, col: +col, row: +row, layer })

const output = { cols: COLS, rows: ROWS, tiles }
const outPath = join(__dirname, '..', 'public', 'tilemap-village.json')

writeFileSync(outPath, JSON.stringify(output, null, 2))

const usage = {}
for (const t of tiles) {
  if (!usage[t.id]) usage[t.id] = 0
  usage[t.id]++
}

console.log(`\u2713 Generated ${outPath}`)
console.log(`  ${tiles.length} tiles`)
console.log(`  ${tiles.filter(t => t.layer === 'ground').length} ground`)
console.log(`  ${tiles.filter(t => t.layer === 'objects').length} objects`)
console.log('\nTile usage:')
for (const [id, cnt] of Object.entries(usage).sort((a, b) => b[1] - a[1]))
  console.log(`  ${id}: ${cnt}`)
