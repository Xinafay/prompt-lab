import { sanitizeJsonPreviewValue, visibleJsonEntries } from "../jsonPreview";

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
    return compactText(JSON.stringify(sanitizeJsonPreviewValue(value)));
  } catch {
    return String(value);
  }
}

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(sanitizeJsonPreviewValue(value), null, 2) ?? "undefined";
  } catch {
    return String(value);
  }
}

function isInspectable(value: unknown): value is Record<string, unknown> | unknown[] {
  return value !== null && typeof value === "object";
}

function JsonTree({ depth = 0, value }: { depth?: number; value: unknown }) {
  if (!isInspectable(value)) {
    return <span className="json-tree-leaf">{previewValue(value)}</span>;
  }

  const entries = visibleJsonEntries(value);
  if (entries.length === 0) {
    return <span className="json-tree-leaf">{Array.isArray(value) ? "[]" : "{}"}</span>;
  }

  return (
    <ul className="json-tree-list">
      {entries.map(([key, child]) => (
        <li className="json-tree-item" key={`${depth}-${key}`}>
          {isInspectable(child) ? (
            <details open={depth < 1}>
              <summary>
                <span className="json-tree-key">{key}</span>
                <span>{describeValue(child)}</span>
              </summary>
              <JsonTree depth={depth + 1} value={child} />
            </details>
          ) : (
            <div className="json-tree-row">
              <span className="json-tree-key">{key}</span>
              <span>{previewValue(child)}</span>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
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
      {isInspectable(value) ? (
        <details className="value-tree" open>
          <summary>Explore keys</summary>
          <JsonTree value={value} />
        </details>
      ) : null}
      <details>
        <summary>Raw JSON</summary>
        <pre>{formatJson(value)}</pre>
      </details>
    </div>
  );
}
