import type { FieldPath, FieldValues, UseFormSetError } from 'react-hook-form';
import { ApiError } from './api-client';

export function applyApiFieldErrors<T extends FieldValues>(error: unknown, setError: UseFormSetError<T>) {
  if (!(error instanceof ApiError) || typeof error.details !== 'object' || error.details === null) return false;
  const fieldErrors = (error.details as { fieldErrors?: unknown }).fieldErrors;
  if (!Array.isArray(fieldErrors)) return false;

  let applied = false;
  for (const fieldError of fieldErrors) {
    if (typeof fieldError !== 'object' || fieldError === null) continue;
    const { field, reason } = fieldError as { field?: unknown; reason?: unknown };
    if (typeof field !== 'string' || typeof reason !== 'string') continue;
    setError(field as FieldPath<T>, { type: 'server', message: reason });
    applied = true;
  }
  return applied;
}
