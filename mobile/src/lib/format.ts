import type { CarCandidate } from '@/api/types';

export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

export function carName(car: Pick<CarCandidate, 'make' | 'model'>): string {
  return `${car.make} ${car.model}`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}
