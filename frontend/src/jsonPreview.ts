function isTechnicalJsonKey(key: string): boolean {
  return key.startsWith("_");
}

export function visibleJsonEntries(
  value: Record<string, unknown> | unknown[]
): Array<readonly [string, unknown]> {
  if (Array.isArray(value)) {
    return value.map((item, index) => [String(index), item] as const);
  }
  return Object.entries(value).filter(([key]) => !isTechnicalJsonKey(key));
}

export function sanitizeJsonPreviewValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeJsonPreviewValue(item));
  }
  if (value === null || typeof value !== "object") {
    return value;
  }
  return Object.fromEntries(
    Object.entries(value)
      .filter(([key]) => !isTechnicalJsonKey(key))
      .map(([key, child]) => [key, sanitizeJsonPreviewValue(child)])
  );
}
