interface ProgressBarProps {
  percent: number;
  label?: string;
  showPercent?: boolean;
}

export default function ProgressBar({ percent, label, showPercent = true }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, percent));
  return (
    <div>
      {(label || showPercent) && (
        <div className="flex items-center justify-between text-[13px] text-muted-foreground mb-2">
          {label && <span>{label}</span>}
          {showPercent && <span className="font-semibold">{Math.round(clamped)}%</span>}
        </div>
      )}
      <div className="w-full bg-border rounded-full h-1.5">
        <div
          className="bg-primary h-1.5 rounded-full transition-all duration-500"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
