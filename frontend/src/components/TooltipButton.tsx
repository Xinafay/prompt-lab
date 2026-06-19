import type { ButtonHTMLAttributes, ReactNode } from "react";

interface TooltipButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  disabledReason?: string | null;
}

export function TooltipButton({
  children,
  disabled,
  disabledReason,
  ...buttonProps
}: TooltipButtonProps) {
  const tooltip = disabled ? disabledReason : null;
  const button = (
    <button {...buttonProps} disabled={disabled} type={buttonProps.type ?? "button"}>
      {children}
    </button>
  );

  if (!tooltip) {
    return button;
  }

  return (
    <span
      aria-label={tooltip}
      className="disabled-tooltip-wrapper"
      data-tooltip={tooltip}
      tabIndex={0}
    >
      {button}
    </span>
  );
}
