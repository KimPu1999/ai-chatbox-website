import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MetricCard } from './components';

describe('platform control center components', () => {
  it('renders real metric labels and values accessibly', () => {
    render(<MetricCard label="Total users" value={42} hint="Active accounts" />);
    expect(screen.getByText('Total users')).toBeTruthy();
    expect(screen.getByText('42')).toBeTruthy();
    expect(screen.getByText('Active accounts')).toBeTruthy();
  });
});
