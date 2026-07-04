import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import type { Project, ProxyStatus } from '../types';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function extractErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  const raw = String(error ?? '').trim();
  if (!raw) {
    return fallback;
  }

  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed === 'string' && parsed.trim()) {
      return parsed;
    }
    if (parsed && typeof parsed === 'object') {
      const detail = (parsed as { detail?: unknown }).detail;
      if (typeof detail === 'string' && detail.trim()) {
        return detail;
      }
    }
  } catch {
    // Keep raw string fallback below.
  }

  return raw;
}

export function commandErrorMessage(fallback: string, output?: string, error?: string): string {
  const details = [error, output].filter(Boolean).join('\n').trim();
  return details ? `${fallback}:\n\n${details}` : fallback;
}

// When the proxy (or the privileged standard-ports forwarder) is not active on
// 80/443, the domain is only reachable on the explicit proxy port.
export function computeProjectUrl(project: Project, status: ProxyStatus | null, path = ''): string {
  const protocol = project.httpsEnabled ? 'https' : 'http';
  let host = project.domain;
  if (status) {
    const proxyActive = project.httpsEnabled ? status.proxyHttpsActive : status.proxyHttpActive;
    const standardActive = project.httpsEnabled ? status.standardHttpsActive : status.standardHttpActive;
    if (!proxyActive || !standardActive) {
      const port = project.httpsEnabled ? status.proxyPort : status.proxyHttpPort;
      host = `${project.domain}:${port}`;
    }
  }
  return `${protocol}://${host}${path}`;
}

export function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString();
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'running':
      return 'text-[var(--success-text)]';
    case 'stopped':
      return 'text-[var(--text-2)]';
    case 'starting':
    case 'stopping':
      return 'text-[var(--warning-text)]';
    case 'error':
      return 'text-[var(--danger-text)]';
    default:
      return 'text-[var(--text-2)]';
  }
}

export function statusDotClass(status: string): string {
  switch (status) {
    case 'running':
      return 'status-dot status-dot-running';
    case 'starting':
    case 'stopping':
      return 'status-dot status-dot-busy';
    case 'error':
      return 'status-dot status-dot-error';
    default:
      return 'status-dot status-dot-stopped';
  }
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + '...';
}
