import { useTranslation } from "react-i18next";
import { Loader2, CheckCircle } from "lucide-react";
import type { JobTimeline } from "../lib/timeline";

/** Compact live view of what the agent is doing on each job being applied to. */
export default function ApplyTimeline({ timelines }: { timelines: JobTimeline[] }) {
  const { t } = useTranslation("jobs");
  if (!timelines.length) return null;
  return (
    <div className="mt-3 space-y-3 w-full" data-testid="apply-timeline">
      {timelines.map((tl) => (
        <div key={tl.url} className="text-[12px]">
          <div className="flex items-center gap-2 font-medium text-foreground">
            {tl.finished ? (
              <CheckCircle className="w-3.5 h-3.5 text-green-600" />
            ) : (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
            )}
            <span className="truncate">
              {tl.title || tl.url}
              {tl.company ? ` · ${tl.company}` : ""}
            </span>
            {tl.step > 0 && !tl.finished && (
              <span className="ml-auto text-muted-foreground flex-shrink-0">{t("timeline.step", { n: tl.step })}</span>
            )}
          </div>
          <ul className="ml-5 mt-1 space-y-0.5 text-muted-foreground">
            {tl.entries.map((e, i) => (
              <li key={i} className="truncate">{e}</li>
            ))}
            {tl.goal && !tl.finished && (
              <li className="truncate text-foreground" data-testid="timeline-goal">
                {t("timeline.now", { goal: tl.goal })}
              </li>
            )}
          </ul>
        </div>
      ))}
    </div>
  );
}
