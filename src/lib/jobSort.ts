import type { Job } from "./types";

export type JobSort = "match" | "newest";

const byNewest = (a: Job, b: Job) => (b.collected_at || "").localeCompare(a.collected_at || "");

/** Sort jobs by match score (highest first, unscored last) or by newest collected. */
export function sortJobs(jobs: Job[], sort: JobSort): Job[] {
  const out = [...jobs];
  if (sort === "match") {
    out.sort((a, b) => {
      const sa = typeof a.match_score === "number" ? a.match_score : -1;
      const sb = typeof b.match_score === "number" ? b.match_score : -1;
      return sb - sa || byNewest(a, b);
    });
  } else {
    out.sort(byNewest);
  }
  return out;
}
