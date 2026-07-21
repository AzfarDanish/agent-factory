export type Layer = 'ground' | 'objects'

export interface PlacedTile {
  id: string
  col: number
  row: number
  layer: Layer
}

export interface MapData {
  cols: number
  rows: number
  tiles: PlacedTile[]
}
