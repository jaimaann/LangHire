import type { ReactNode } from "react";

interface SectionProps {
  title: string;
  children: ReactNode;
  className?: string;
}

export default function Section({ title, children, className = "mb-5" }: SectionProps) {
  return (
    <div className={`card ${className}`}>
      <h3 className="text-sm font-bold text-foreground mb-4">{title}</h3>
      {children}
    </div>
  );
}
