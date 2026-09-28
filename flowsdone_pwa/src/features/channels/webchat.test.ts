import { describe, expect, it } from 'vitest'
import type { ChannelConnection } from '@/core/admin/types'
import { originsOf, parseOrigins, webchatSnippet } from './webchat'

const connection = (over: Partial<ChannelConnection> = {}): ChannelConnection => ({
  id: 'c9', project_id: 'p1', agent_id: 'a1', channel_type: 'webchat', external_id: 'wc_key', display_name: null,
  has_credentials: false, config: {}, status: 'active', created_at: '', updated_at: '',
  webchat: { script_url: 'https://chat.flowsdone.com/agent-chat-widget.js', ws_url: 'wss://chat.flowsdone.com/ws' },
  ...over,
})

describe('dominios permitidos', () => {
  it('uno por línea o separados por comas, sin vacíos', () => {
    expect(parseOrigins(' https://a.com\n\nb.com, https://c.com ')).toEqual(['https://a.com', 'b.com', 'https://c.com'])
    expect(parseOrigins('  ')).toEqual([])
  })

  it('lee los del config e ignora valores que no son texto', () => {
    expect(originsOf(connection({ config: { allowed_origins: ['https://a.com', 3] } }))).toEqual(['https://a.com'])
    expect(originsOf(connection())).toEqual([])
    expect(originsOf(null)).toEqual([])
  })
})

describe('fragmento para la web', () => {
  it('incluye el CSS, el WebSocket del gateway y la clave del canal', () => {
    const snippet = webchatSnippet(connection())!
    expect(snippet).toContain('href="https://chat.flowsdone.com/agent-chat-widget.css"')
    expect(snippet).toContain('wsUrl: "wss://chat.flowsdone.com/ws"')
    expect(snippet).toContain('channelKey: "wc_key"')
    expect(snippet).toContain('<script src="https://chat.flowsdone.com/agent-chat-widget.js" defer></script>')
  })

  it('sin las URLs del gateway no hay fragmento', () => {
    expect(webchatSnippet(connection({ webchat: null }))).toBeNull()
  })
})
