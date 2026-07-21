import { readFileSync } from 'fs'
import { join } from 'path'
import VillageView from './village-view'

export default function TilemapPage() {
  const p = join(process.cwd(), 'public', 'tilemap-village.json')
  const data = JSON.parse(readFileSync(p, 'utf-8'))
  return <VillageView data={data} />
}
