import type { InventoryItem } from '@/types/api';

/**
 * Low stock = available stock at or below the backend-supplied threshold.
 * Returns null (unknown) when either value is missing — never guesses a threshold.
 */
export function isLowStock(item: Pick<InventoryItem, 'available' | 'lowStockThreshold'>): boolean | null {
  if (item.available === null || item.lowStockThreshold === null) return null;
  return item.available <= item.lowStockThreshold;
}
