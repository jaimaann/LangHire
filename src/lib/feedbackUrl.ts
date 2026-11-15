const REPO_URL = "https://github.com/jaimaann/LangHire";

export const CATEGORY_KEYS = ["featureRequest", "bugReport", "generalFeedback"] as const;
// Discussion category slugs on GitHub; an unknown slug just shows GitHub's picker.
const CATEGORY_SLUG: Record<string, string> = {
  featureRequest: "feature-request",
  bugReport: "bug-report",
  generalFeedback: "general-feedback",
};

/**
 * A prefilled "new discussion" URL. The user posts it from their own GitHub
 * account in the browser — the app no longer ships a GitHub token in its
 * bundle (anyone could extract it), and release builds never had one anyway.
 */
export function buildDiscussionUrl(title: string, body: string, categoryKey: string): string {
  const params = new URLSearchParams({
    category: CATEGORY_SLUG[categoryKey] ?? "general-feedback",
    title,
    body,
  });
  return `${REPO_URL}/discussions/new?${params.toString()}`;
}

