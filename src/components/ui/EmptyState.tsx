import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
}

export default function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="card text-center mb-5">
      <div className="py-6">
        <Icon className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
        <h3 className="text-lg font-bold text-foreground mb-2">{title}</h3>
        <p className="text-[13px] text-muted-foreground mb-5">{description}</p>
        {action}
      </div>
    </div>
  );
}
