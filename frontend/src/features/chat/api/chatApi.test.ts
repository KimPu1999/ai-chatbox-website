import { describe, expect, it } from 'vitest';
import { parseSseBlock } from './chatApi';

describe('SSE parser', () => {
  it('parses event ids, comments, CRLF and multiline JSON data', () => {
    const result = parseSseBlock('id: run:1\r\nevent: message.delta\r\n: heartbeat\r\ndata: {"delta":\r\ndata: "hello"}\r\n')!;
    expect(result.id).toBe('run:1');
    expect(result.event).toBe('message.delta');
    expect(result.payload.delta).toBe('hello');
  });
});
