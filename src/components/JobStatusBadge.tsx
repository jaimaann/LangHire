import { CheckCircle, XCircle, Clock, Ban, Loader2, HelpCircle, SkipForward, FlaskConical } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { JobStatus } from "../lib/types";

const STATUS_ICONS: Record<JobStatus, typeof CheckCircle> = {
  pending: Clock,
  applied: CheckCircle,
  failed: XCircle,
  blocked: Ban,
  in_progress: Loader2,
  needs_input: HelpCircle,
  skipped: SkipForward,
  test_passed: FlaskConical,
};

const STATUS_STYLES: Record<JobStatus, { color: string; bg: string }> = {
  pending: { color: "text-amber-700", bg: "bg-amber-50" },
  applied: { color: "text-success", bg: "bg-[#F0FFF0]" },
  failed: { color: "text-destructive", bg: "bg-[#FFF0F0]" },
  blocked: { color: "text-muted-foreground", bg: "bg-[#F7F7F7]" },
  in_progress: { color: "text-primary", bg: "bg-[#FFF0F3]" },
  needs_input: { color: "text-violet-700", bg: "bg-violet-50" },
  skipped: { color: "text-muted-foreground", bg: "bg-secondary" },
  test_passed: { color: "text-sky-700", bg: "bg-sky-50" },
};

/** i18n key (in the "jobs" namespace) of each status label. */
const STATUS_LABEL_KEYS: Record<JobStatus, string> = {
  pending: "status.pending",
  applied: "status.applied",
  failed: "status.failed",
  blocked: "status.blocked",
  in_progress: "status.inProgress",
  needs_input: "status.needsInput",
  skipped: "status.skipped",
  test_passed: "status.testPassed",
};

/** Colored pill with an icon and the translated label of a job status. */
export default function JobStatusBadge({ status }: { status: JobStatus }) {
  const { t } = useTranslation("jobs");
  const known = status in STATUS_STYLES ? status : "pending";
  const Icon = STATUS_ICONS[known];
  const styles = STATUS_STYLES[known];
  return (
    <span
      data-testid={`status-badge-${known}`}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold flex-shrink-0 ${styles.bg} ${styles.color}`}
    >
      <Icon className="w-3 h-3" /> {t(STATUS_LABEL_KEYS[known])}
    </span>
  );
}
