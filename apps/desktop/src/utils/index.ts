import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString();
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'running':
      return 'text-green-600';
    case 'stopped':
      return 'text-gray-600';
    case 'starting':
    case 'stopping':
      return 'text-yellow-600';
    case 'error':
      return 'text-red-600';
    default:
      return 'text-gray-600';
  }
}

export function getStatusIcon(status: string): string {
  switch (status) {
    case 'running':
      return '●';
    case 'stopped':
      return '○';
    case 'starting':
    case 'stopping':
      return '◐';
    case 'error':
      return '✕';
    default:
      return '○';
  }
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + '...';
}
