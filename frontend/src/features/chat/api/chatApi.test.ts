import { describe, expect, it, vi } from 'vitest';
import { parseSseBlock, streamGeneration } from './chatApi';

vi.mock('../../../api/client', () => ({
  api: { get: vi.fn() },
  loadCsrfToken: vi.fn().mockResolvedValue('csrf-test'),
}));

describe('SSE parser', () => {
  it('parses event ids, comments, CRLF and multiline JSON data', () => {
    const result = parseSseBlock('id: run:1\r\nevent: message.delta\r\n: heartbeat\r\ndata: {"delta":\r\ndata: "hello"}\r\n')!;
    expect(result.id).toBe('run:1');
    expect(result.event).toBe('message.delta');
    expect(result.payload.delta).toBe('hello');
  });

  it('reassembles fragmented UTF-8 SSE and ignores duplicate event ids', async () => {
    const encoder = new TextEncoder();
    const chunks = [
      'id: run:start\nevent: run.started\ndata: {"run_id":"r1"}\n\n',
      'id: run:delta\nevent: message.delta\ndata: {"delta":"မင်',
      '္ဂလာ"}\n\n',
      'id: run:delta\nevent: message.delta\ndata: {"delta":"မင်္ဂလာ"}\n\n',
      'id: run:complete\nevent: run.completed\ndata: {"run_id":"r1"}\n\n',
    ];
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, { status: 200 })));
    const events: string[] = [];
    await streamGeneration(
      'conversation-1',
      { content: 'hello', idempotency_key: 'key-1' },
      { onEvent: (event, payload) => { if (event === 'message.delta') events.push(payload.delta || ''); } },
      new AbortController().signal,
    );
    expect(events).toEqual(['မင်္ဂလာ']);
  });
});
