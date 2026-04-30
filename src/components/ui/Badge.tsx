import type { ReactNode } from "react";

type BadgeVariant = "success" | "error" | "warning" | "info" | "muted" | "primary";

const VARIANT_STYLES: Record<BadgeVariant, string> = {
  success: "bg-[#F0FFF0] text-success",
  error: "bg-[#FFF0F0] text-destructive",
  warning: "bg-[#FFF8F0] text-warning",
  info: "bg-[#F0F4FF] text-[#3B5998]",
  muted: "bg-[#F7F7F7] text-muted-foreground",
  primary: "bg-[#FFF0F3] text-primary",
};

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
}

export default function Badge({ variant = "muted", children, className = "" }: BadgeProps) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${VARIANT_STYLES[variant]} ${className}`}>
      {children}
    </span>
  );
}
