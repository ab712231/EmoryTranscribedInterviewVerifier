import {
  forwardRef,
  useId,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";
import { AlertIcon, CheckIcon } from "./Icon";
import "./ui.css";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "quiet";
  full?: boolean;
  busy?: boolean;
  busyLabel?: string;
};

export function Button({
  variant = "primary",
  full = false,
  busy = false,
  busyLabel,
  children,
  className,
  disabled,
  ...rest
}: ButtonProps) {
  const classes = ["button", `button--${variant}`];
  if (full) {
    classes.push("button--full");
  }
  if (className) {
    classes.push(className);
  }

  return (
    <button
      className={classes.join(" ")}
      disabled={disabled || busy}
      aria-busy={busy}
      {...rest}
    >
      {busy ? (
        <>
          <span className="spinner" aria-hidden="true" />
          {busyLabel ?? children}
        </>
      ) : (
        children
      )}
    </button>
  );
}

interface FieldShellProps {
  label: string;
  hint?: string;
  error?: string;
  children: (props: { id: string; describedBy: string | undefined; invalid: boolean }) => ReactNode;
}

function FieldShell({ label, hint, error, children }: FieldShellProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;

  const described: string[] = [];
  if (hint) {
    described.push(hintId);
  }
  if (error) {
    described.push(errorId);
  }
  const describedBy = described.length > 0 ? described.join(" ") : undefined;

  return (
    <div className={`field${error ? " field--invalid" : ""}`}>
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      {hint ? (
        <span className="field__hint" id={hintId}>
          {hint}
        </span>
      ) : null}
      {children({ id, describedBy, invalid: Boolean(error) })}
      {error ? (
        <p className="field__error" id={errorId}>
          <AlertIcon size={18} />
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  );
}

type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id"> & {
  label: string;
  hint?: string;
  error?: string;
};

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, hint, error, ...rest },
  ref
) {
  return (
    <FieldShell label={label} hint={hint} error={error}>
      {({ id, describedBy, invalid }) => (
        <input
          {...rest}
          ref={ref}
          id={id}
          className="field__control"
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
        />
      )}
    </FieldShell>
  );
});

type TextAreaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> & {
  label: string;
  hint?: string;
  error?: string;
};

export function TextArea({ label, hint, error, ...rest }: TextAreaProps) {
  return (
    <FieldShell label={label} hint={hint} error={error}>
      {({ id, describedBy, invalid }) => (
        <textarea
          {...rest}
          id={id}
          className="field__control"
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
        />
      )}
    </FieldShell>
  );
}

export function Callout({
  tone = "info",
  title,
  children,
  role,
}: {
  tone?: "info" | "error" | "success";
  title?: string;
  children?: ReactNode;
  role?: "alert" | "status";
}) {
  const Glyph = tone === "success" ? CheckIcon : AlertIcon;
  return (
    <div className={`callout callout--${tone}`} role={role}>
      {tone === "info" ? null : <Glyph size={20} />}
      <div className="callout__body">
        {title ? <p className="callout__title">{title}</p> : null}
        {children ? <div className="callout__text">{children}</div> : null}
      </div>
    </div>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}
