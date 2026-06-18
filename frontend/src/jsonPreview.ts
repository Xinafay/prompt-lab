export function visibleJsonEntries(
  value: Record<string, unknown> | unknown[]
): Array<readonly [string, unknown]> {
  if (Array.isArray(value)) {
    return value.map((item, index) => [String(index), item] as const);
  }
  return Object.entries(value).filter(([key]) => !key.startsWith("_"));
}
