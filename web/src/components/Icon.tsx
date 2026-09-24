interface IconProps {
  size?: number;
  className?: string;
}

function svgProps(size: number) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
    focusable: false,
  };
}

export function CheckIcon({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

export function CrossIcon({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

export function QuestionIcon({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3" />
      <path d="M12 17h.01" />
      <circle cx="12" cy="12" r="9" />
    </svg>
  );
}

export function AlertIcon({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.9 2.4 17a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
    </svg>
  );
}

export function MailIcon({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m2.5 6.5 8.4 5.6a2 2 0 0 0 2.2 0l8.4-5.6" />
    </svg>
  );
}

export function ArrowLeftIcon({ size = 20, className }: IconProps) {
  return (
    <svg {...svgProps(size)} className={className}>
      <path d="M19 12H5" />
      <path d="m12 19-7-7 7-7" />
    </svg>
  );
}
