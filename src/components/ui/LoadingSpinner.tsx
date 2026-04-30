import { Loader2 } from "lucide-react";

interface LoadingSpinnerProps {
  className?: string;
}

export default function LoadingSpinner({ className = "h-64" }: LoadingSpinnerProps) {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <Loader2 className="w-8 h-8 animate-spin text-primary" />
    </div>
  );
}
