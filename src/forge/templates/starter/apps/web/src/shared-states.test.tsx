import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { EmptyState, ErrorState, LoadingState } from '@app/shared-ui/components/states';

it('the loading part is a status with its label', () => {
  render(<LoadingState label="Loading orders" />);
  expect(screen.getByRole('status', { name: 'Loading orders' })).toBeTruthy();
});

it('the empty part shows its title, description and action', () => {
  render(<EmptyState title="No orders yet" description="Orders you add appear here." action={<button type="button">Add order</button>} />);
  expect(screen.getByText('No orders yet')).toBeTruthy();
  expect(screen.getByText('Orders you add appear here.')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Add order' })).toBeTruthy();
});

it('the error part is an alert and its retry button calls onRetry once', () => {
  const onRetry = vi.fn();
  render(<ErrorState message="The server is busy. Try again in a minute." onRetry={onRetry} />);
  expect(screen.getByRole('alert').textContent).toContain('The server is busy. Try again in a minute.');
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(onRetry).toHaveBeenCalledTimes(1);
});

it('the error part has no retry button without onRetry', () => {
  render(<ErrorState message="You cannot see this page." />);
  expect(screen.getByRole('alert')).toBeTruthy();
  expect(screen.queryByRole('button')).toBeNull();
});

it('the retry button inside a form does not submit it', () => {
  const onSubmit = vi.fn((event: { preventDefault: () => void }) => event.preventDefault());
  render(
    <form onSubmit={onSubmit}>
      <ErrorState message="Saving failed. Try again." onRetry={() => undefined} />
    </form>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(onSubmit).not.toHaveBeenCalled();
});
