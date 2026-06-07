interface ValuePreviewProps {
  value: unknown;
}

function compactText(value: string, maxLength = 220): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) {
    return normalized || "(empty string)";
  }
  return `${normalized.slice(0, maxLength)}...`;
}

function compactJson(value: unknown): string {
  try {
    return compactText(JSON.stringify(value));
  } catch {
    return String(value);
  }
}

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? "undefined";
  } catch {
    return String(value);
  }
}

export function describeValue(value: unknown): string {
  if (value === null) {
    return "null";
  }
  if (Array.isArray(value)) {
    return `array | ${value.length} item${value.length === 1 ? "" : "s"}`;
  }
  if (typeof value === "object") {
    const keyCount = Object.keys(value).length;
    return `object | ${keyCount} key${keyCount === 1 ? "" : "s"}`;
  }
  if (typeof value === "string") {
    return `string | ${value.length} char${value.length === 1 ? "" : "s"}`;
  }
  if (typeof value === "boolean") {
    return "boolean";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? "number" : "number | non-finite";
  }
  if (value === undefined) {
    return "undefined";
  }
  return typeof value;
}

function previewValue(value: unknown): string {
  if (value === null) {
    return "null";
  }
  if (typeof value === "string") {
    return compactText(value);
  }
  if (
    Array.isArray(value) ||
    (typeof value === "object" && value !== null) ||
    typeof value === "boolean" ||
    typeof value === "number"
  ) {
    return compactJson(value);
  }
  if (value === undefined) {
    return "undefined";
  }
  return compactText(String(value));
}

export function ValuePreview({ value }: ValuePreviewProps) {
  return (
    <div className="value-preview">
      <p>{previewValue(value)}</p>
      <details>
        <summary>Raw JSON</summary>
        <pre>{formatJson(value)}</pre>
      </details>
    </div>
  );
}
