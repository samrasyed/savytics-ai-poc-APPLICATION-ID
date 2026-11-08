// Formats an ISO timestamp as a short local date and time.
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

// Formats a millisecond duration as seconds with one decimal place.
export function formatSeconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`;
}
