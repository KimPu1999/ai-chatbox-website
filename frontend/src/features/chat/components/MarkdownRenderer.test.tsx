import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MarkdownRenderer } from './MarkdownRenderer';

describe('MarkdownRenderer', () => {
  it('renders markdown and strips unsafe links/html', () => {
    const view = render(<MarkdownRenderer content={'**safe**\n\n<a href="javascript:alert(1)">bad</a>\n\n[bad](javascript:alert(1))'} />);
    expect(view.getByText('safe')).toBeDefined();
    expect(view.container.querySelector('script')).toBeNull();
    expect(view.container.querySelector('a[href^="javascript:"]')).toBeNull();
  });
});
