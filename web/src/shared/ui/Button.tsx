import type { ButtonHTMLAttributes } from "react";
import s from "./ui.module.css";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { tone?: "primary" | "quiet" | "danger" };

export function Button({ tone = "primary", className, ...rest }: Props) {
  const toneClass = tone === "quiet" ? s.quiet : tone === "danger" ? s.danger : "";
  return <button type="button" {...rest} className={[s.button, toneClass, className].filter(Boolean).join(" ")} />;
}
