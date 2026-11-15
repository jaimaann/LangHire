import { useState } from "react";
import { Send, ExternalLink, CheckCircle, MessageSquare } from "lucide-react";
import { useTranslation } from "react-i18next";
import { buildDiscussionUrl, CATEGORY_KEYS } from "../lib/feedbackUrl";

async function openExternal(url: string): Promise<void> {
  try {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
  } catch {
    window.open(url, "_blank", "noopener,noreferrer");
  }
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
    setError(null);
    setSubmitting(true);
    try {
      let body = description.trim();
      if (email.trim()) body += `\n\n---\n*Contact: ${email.trim()}*`;

      const url = buildDiscussionUrl(title.trim(), body, categoryKey);
      await openExternal(url);
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
                      ? "bg-foreground text-background"
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
