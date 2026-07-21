export interface TileDef {
  id: string
  name: string
  width: number
  height: number
  category: string
  hasDay: boolean
  hasNight: boolean
}

export const TILES: TileDef[] = [
  { id: "BRIDGE", name: "BRIDGE", width: 96, height: 48, category: "BRIDGE", hasDay: true, hasNight: true },
  { id: "CHURCH", name: "CHURCH", width: 128, height: 112, category: "CHURCH", hasDay: true, hasNight: true },
  { id: "FENCE 1", name: "FENCE 1", width: 16, height: 16, category: "FENCE", hasDay: true, hasNight: true },
  { id: "FENCE 2", name: "FENCE 2", width: 16, height: 16, category: "FENCE", hasDay: true, hasNight: true },
  { id: "GRASS DETAIL 1", name: "GRASS DETAIL 1", width: 16, height: 16, category: "GRASS", hasDay: true, hasNight: true },
  { id: "GRASS DETAIL 2", name: "GRASS DETAIL 2", width: 16, height: 16, category: "GRASS", hasDay: true, hasNight: true },
  { id: "GRASS DETAIL 3", name: "GRASS DETAIL 3", width: 16, height: 16, category: "GRASS", hasDay: true, hasNight: true },
  { id: "GRASS DETAIL 4", name: "GRASS DETAIL 4", width: 16, height: 16, category: "GRASS", hasDay: true, hasNight: true },
  { id: "GRASS DETAIL 5", name: "GRASS DETAIL 5", width: 16, height: 16, category: "GRASS", hasDay: true, hasNight: true },
  { id: "GRASS DETAIL 6", name: "GRASS DETAIL 6", width: 16, height: 16, category: "GRASS", hasDay: true, hasNight: true },
  { id: "GRASS TILE", name: "GRASS TILE", width: 16, height: 16, category: "GRASS", hasDay: true, hasNight: true },
  { id: "GROUND DETAIL 1", name: "GROUND DETAIL 1", width: 16, height: 16, category: "GROUND", hasDay: true, hasNight: true },
  { id: "GROUND DETAIL 2", name: "GROUND DETAIL 2", width: 16, height: 16, category: "GROUND", hasDay: true, hasNight: true },
  { id: "GROUND DETAIL 3", name: "GROUND DETAIL 3", width: 16, height: 16, category: "GROUND", hasDay: true, hasNight: true },
  { id: "GROUND DETAIL 4", name: "GROUND DETAIL 4", width: 16, height: 16, category: "GROUND", hasDay: true, hasNight: true },
  { id: "GROUND DETAIL 5", name: "GROUND DETAIL 5", width: 16, height: 16, category: "GROUND", hasDay: true, hasNight: true },
  { id: "GROUND TILE", name: "GROUND TILE", width: 16, height: 16, category: "GROUND", hasDay: true, hasNight: true },
  { id: "HOUSE 1", name: "HOUSE 1", width: 80, height: 112, category: "HOUSE", hasDay: true, hasNight: true },
  { id: "HOUSE 2", name: "HOUSE 2", width: 128, height: 112, category: "HOUSE", hasDay: true, hasNight: true },
  { id: "PIT", name: "PIT", width: 32, height: 48, category: "PIT", hasDay: true, hasNight: true },
  { id: "STAIRS", name: "STAIRS", width: 32, height: 64, category: "STAIRS", hasDay: true, hasNight: true },
  { id: "TERRAIN SET 1", name: "TERRAIN SET 1", width: 48, height: 48, category: "TERRAIN", hasDay: true, hasNight: true },
  { id: "TERRAIN SET 2", name: "TERRAIN SET 2", width: 48, height: 48, category: "TERRAIN", hasDay: true, hasNight: true },
  { id: "TERRAIN SET 3", name: "TERRAIN SET 3", width: 48, height: 64, category: "TERRAIN", hasDay: true, hasNight: true },
  { id: "TERRAIN SET 3 CURVES", name: "TERRAIN SET 3 CURVES", width: 32, height: 32, category: "TERRAIN", hasDay: true, hasNight: true },
  { id: "TERRAIN SET 4", name: "TERRAIN SET 4", width: 48, height: 64, category: "TERRAIN", hasDay: true, hasNight: true },
  { id: "TERRAIN SET 4 CURVES", name: "TERRAIN SET 4 CURVES", width: 32, height: 48, category: "TERRAIN", hasDay: true, hasNight: true },
  { id: "TERRAIN SET 5", name: "TERRAIN SET 5", width: 48, height: 48, category: "TERRAIN", hasDay: true, hasNight: true },
  { id: "TREE 1", name: "TREE 1", width: 48, height: 48, category: "TREE", hasDay: true, hasNight: true },
  { id: "TREE 2", name: "TREE 2", width: 48, height: 48, category: "TREE", hasDay: true, hasNight: true },
  { id: "TREE 3", name: "TREE 3", width: 48, height: 48, category: "TREE", hasDay: true, hasNight: true },
  { id: "WATER DETAIL 1", name: "WATER DETAIL 1", width: 16, height: 16, category: "WATER", hasDay: true, hasNight: true },
  { id: "WATER DETAIL 2", name: "WATER DETAIL 2", width: 16, height: 16, category: "WATER", hasDay: true, hasNight: true },
  { id: "WATER DETAIL 3", name: "WATER DETAIL 3", width: 16, height: 16, category: "WATER", hasDay: true, hasNight: true },
  { id: "WATER DETAIL 4", name: "WATER DETAIL 4", width: 16, height: 16, category: "WATER", hasDay: true, hasNight: true },
  { id: "WATER DETAIL 5", name: "WATER DETAIL 5", width: 16, height: 16, category: "WATER", hasDay: true, hasNight: true },
  { id: "WATER TILE", name: "WATER TILE", width: 16, height: 16, category: "WATER", hasDay: true, hasNight: true },
]

export const TILE_MAP: Record<string, TileDef> = {}
TILES.forEach(t => { TILE_MAP[t.id] = t })
