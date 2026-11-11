import { fireEvent, render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MessageComposer } from './MessageComposer';

describe('MessageComposer', () => {
  it('sends with Enter and keeps a newline for Shift+Enter', async () => {
    const onSend = vi.fn().mockResolvedValue(true);
    const view = render(<MessageComposer pending={false} onSend={onSend} />);
    const input = view.getByLabelText('Message PyChat AI');
    fireEvent.change(input, { target: { value: 'hello' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });
    expect(onSend).toHaveBeenCalledWith('hello');
    fireEvent.change(input, { target: { value: 'line one' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter', shiftKey: true });
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it('does not submit an empty message', () => {
    const onSend = vi.fn();
    const view = render(<MessageComposer pending={false} onSend={onSend} />);
    fireEvent.submit(view.container.querySelector('form')!);
    expect(onSend).not.toHaveBeenCalled();
  });
});
