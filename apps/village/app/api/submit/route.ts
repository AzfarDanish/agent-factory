import { NextRequest, NextResponse } from 'next/server'
import { writeFileSync, existsSync, mkdirSync } from 'fs'
import { join } from 'path'
import { execSync } from 'child_process'

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()

    // Handle pipeline trigger request
    if (body.run_pipeline) {
      const scriptPath = join(process.cwd(), '..', '..', 'scripts', 'run_pipeline_once.py')
      const python = process.env.HERMES_VENV_PYTHON || 'python3'
      try {
        const result = execSync(`"${python}" "${scriptPath}"`, {
          cwd: join(process.cwd(), '..', '..'),
          timeout: 30000,
          stdio: 'pipe',
          env: { ...process.env, PATH: process.env.PATH },
        })
        return NextResponse.json({ success: true, pipeline: 'triggered', output: result.toString().trim() })
      } catch (e: any) {
        return NextResponse.json({ success: false, error: `Pipeline error: ${e.message}`, stderr: (e as any).stderr?.toString() }, { status: 500 })
      }
    }

    const { prompt, age_group, style } = body

    if (!prompt || prompt.length < 3) {
      return NextResponse.json({ error: 'Prompt must be at least 3 characters' }, { status: 400 })
    }

    // Build message envelope
    const traceId = crypto.randomUUID()
    const message = {
      id: crypto.randomUUID(),
      type: 'request',
      version: 1,
      timestamp: new Date().toISOString(),
      trace_id: traceId,
      payload: {
        prompt: prompt.trim(),
        age_group: age_group || 'child',
        style: style || 'cartoon',
        quantity: 1,
      },
      metadata: {
        retry_count: 0,
        source: 'user',
      },
    }

    // Write to requests queue
    const queueDir = join(process.cwd(), '..', '..', '.queues', 'coloring')
    if (!existsSync(queueDir)) {
      mkdirSync(queueDir, { recursive: true })
    }
    writeFileSync(join(queueDir, 'requests.jsonl'), JSON.stringify(message) + '\n', { flag: 'a' })

    return NextResponse.json({
      success: true,
      trace_id: traceId,
      message: 'Request submitted',
    })

  } catch (err) {
    console.error('Submit error:', err)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
