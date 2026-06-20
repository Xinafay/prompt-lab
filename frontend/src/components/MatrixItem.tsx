import type { ReactNode } from "react";

export function MatrixItem({
  checkbox,
  badge,
  title,
  meta,
  description,
  className = ""
}: {
  checkbox?: ReactNode;
  badge?: ReactNode;
  title?: ReactNode;
  meta?: ReactNode;
  description?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`validation-matrix-item ${className}`.trim()}>
      {checkbox !== undefined || badge !== undefined ? (
        <div className="validation-matrix-item-toolbar">
          <span>{checkbox}</span>
          <span>{badge}</span>
        </div>
      ) : null}
      {title !== undefined ? (
        <strong className="validation-matrix-item-title">{title}</strong>
      ) : null}
      {meta !== undefined ? (
        <span className="validation-matrix-item-meta">{meta}</span>
      ) : null}
      {description !== undefined ? (
        <p className="validation-matrix-item-description">{description}</p>
      ) : null}
    </div>
  );
}
