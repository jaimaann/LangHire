import type { ApplicationRecord } from "./types";

/** Answers worth a spot-check: guessed by the agent, or entered with low confidence. */
export function countUncertain(record: ApplicationRecord): number {
  return (record.answers || []).filter(
    (a) => a.source === "inferred" || (typeof a.confidence === "number" && a.confidence < 0.6),
  ).length;
}
