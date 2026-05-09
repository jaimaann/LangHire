import { useState } from "react";
import { Send, ExternalLink, CheckCircle, MessageSquare } from "lucide-react";
import { useTranslation } from "react-i18next";

const GITHUB_TOKEN = import.meta.env.VITE_GITHUB_TOKEN || "";
const GITHUB_GRAPHQL_URL = "https://api.github.com/graphql";
const REPO_OWNER = "jaimaann";
const REPO_NAME = "LangHire";

const CATEGORY_KEYS = ["featureRequest", "bugReport", "generalFeedback"] as const;
const CATEGORY_MAP: Record<string, string> = {
  featureRequest: "Feature Request",
  bugReport: "Bug Report",
  generalFeedback: "General Feedback",
};

async function createDiscussion(title: string, body: string, categoryName: string): Promise<string> {
  const headers = { Authorization: `Bearer ${GITHUB_TOKEN}`, "Content-Type": "application/json" };

  const repoRes = await fetch(GITHUB_GRAPHQL_URL, {
    method: "POST",
    headers,
    body: JSON.stringify({
      query: `{ repository(owner: "${REPO_OWNER}", name: "${REPO_NAME}") { id, discussionCategories(first: 25) { nodes { id, name } } } }`,
    }),
  });
  const repoData = await repoRes.json();
  if (repoData.errors) throw new Error(repoData.errors[0].message);

  const repoId = repoData.data.repository.id;
  const cats = repoData.data.repository.discussionCategories.nodes;
  const cat = cats.find((c: { name: string }) => c.name.toLowerCase() === categoryName.toLowerCase()) || cats[0];
  if (!cat) throw new Error("No discussion categories found.");

  const mutRes = await fetch(GITHUB_GRAPHQL_URL, {
    method: "POST",
    headers,
    body: JSON.stringify({
      query: `mutation($repoId: ID!, $catId: ID!, $title: String!, $body: String!) {
        createDiscussion(input: {repositoryId: $repoId, categoryId: $catId, title: $title, body: $body}) {
          discussion { url }
        }
      }`,
      variables: { repoId, catId: cat.id, title, body },
    }),
  });
  const mutData = await mutRes.json();
  if (mutData.errors) throw new Error(mutData.errors[0].message);

  return mutData.data.createDiscussion.discussion.url;
}

export default function Feedback() {
  const { t } = useTranslation("feedback");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryKey, setCategoryKey] = useState<string>(CATEGORY_KEYS[0]);
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!title.trim() || !description.trim()) {
      setError(t("error.fillRequired"));
      return;
    }
    if (!GITHUB_TOKEN) {
      setError(t("error.notConfigured"));
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      let body = description.trim();
      if (email.trim()) body += `\n\n---\n*Contact: ${email.trim()}*`;

      const url = await createDiscussion(title.trim(), body, CATEGORY_MAP[categoryKey]);
      setSuccess(url);
      setTitle("");
      setDescription("");
      setEmail("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("error.submitFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-1">
        <div>
          <h1 className="text-2xl font-bold text-foreground tracking-tight">{t("title")}</h1>
          <p className="text-[13px] text-muted-foreground mt-1">{t("subtitle")}</p>
        </div>
        <a
          href="https://github.com/jaimaann/LangHire/discussions"
          target="_blank"
          rel="noopener noreferrer"
          className="btn-secondary text-xs"
        >
          <MessageSquare className="w-3.5 h-3.5" />
          {t("viewDiscussions")}
        </a>
      </div>

      {error && (
        <div className="error-banner mb-5 mt-5">{error}</div>
      )}

      {success ? (
        <div className="mt-6 card text-center py-10">
          <CheckCircle className="w-12 h-12 text-success mx-auto mb-4" />
          <h2 className="text-lg font-bold mb-2">{t("success.title")}</h2>
          <p className="text-sm text-muted-foreground mb-4">
            {t("success.description")}
          </p>
          <div className="flex items-center justify-center gap-3">
            <a
              href={success}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary text-xs"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              {t("success.viewDiscussion")}
            </a>
            <button onClick={() => setSuccess(null)} className="btn-secondary text-xs">
              {t("success.submitAnother")}
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-6 space-y-5">
          <div className="card">
            <label className="block text-sm font-semibold text-foreground mb-1.5">{t("form.categoryLabel")}</label>
            <div className="flex gap-2">
              {CATEGORY_KEYS.map((c) => (
                <button
                  key={c}
                  onClick={() => setCategoryKey(c)}
                  className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                    categoryKey === c
                      ? "bg-foreground text-white"
                      : "bg-secondary text-muted-foreground hover:bg-border"
                  }`}
                >
                  {t(`categories.${c}`)}
                </button>
              ))}
            </div>
          </div>

          <div className="card">
            <label className="block text-sm font-semibold text-foreground mb-1.5">{t("form.titleLabel")}</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t("form.titlePlaceholder")}
              className="input-base"
            />
          </div>

          <div className="card">
            <label className="block text-sm font-semibold text-foreground mb-1.5">{t("form.descriptionLabel")}</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("form.descriptionPlaceholder")}
              rows={6}
              className="input-base resize-y"
            />
          </div>

          <div className="card">
            <label className="block text-sm font-semibold text-foreground mb-1.5">
              {t("form.emailLabel")} <span className="text-muted-foreground font-normal">{t("form.emailOptional")}</span>
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("form.emailPlaceholder")}
              className="input-base"
            />
            <p className="text-[11px] text-muted-foreground mt-1.5">
              {t("form.emailHelp")}
            </p>
          </div>

          <button
            onClick={handleSubmit}
            disabled={submitting || !title.trim() || !description.trim()}
            className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
            {submitting ? t("form.submitting") : t("form.submit")}
          </button>
        </div>
      )}
    </div>
  );
}
