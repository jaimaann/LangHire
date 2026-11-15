import { useState, useEffect, useCallback } from "react";
import { CheckCircle, XCircle, LogIn, Loader2, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { getAuthStatus, launchLogin } from "../lib/api";
import type { AuthStatus } from "../lib/types";

/** Brand colors for well-known services; everything else uses the app theme. */
const SERVICE_STYLES: Record<string, { nameColor: string; btnClass: string }> = {
  linkedin: { nameColor: "text-[#0A66C2]", btnClass: "bg-[#0A66C2] hover:bg-[#084D93]" },
  gmail: { nameColor: "text-red-600", btnClass: "bg-red-600 hover:bg-red-700" },
};
const DEFAULT_STYLE = { nameColor: "text-foreground", btnClass: "bg-primary hover:bg-primary/90" };

const FALLBACK_NAMES: Record<string, string> = { linkedin: "LinkedIn", gmail: "Gmail" };

/** LinkedIn first, Gmail last, the other job sites in between (backend order). */
function orderServices(ids: string[]): string[] {
  const middle = ids.filter((id) => id !== "linkedin" && id !== "gmail");
  return [
    ...(ids.includes("linkedin") ? ["linkedin"] : []),
    ...middle,
    ...(ids.includes("gmail") ? ["gmail"] : []),
  ];
}

interface LoginCardsProps {
  /** Whether "read verification codes from Gmail" is on; Gmail is optional otherwise. */
  gmailEnabled?: boolean;
}

/**
 * One card per job site that supports logging in (from GET /auth/status),
 * plus Gmail for email verification codes. All logins are optional.
 */
export default function LoginCards({ gmailEnabled = false }: LoginCardsProps) {
  const { t } = useTranslation("settings");
  const [status, setStatus] = useState<AuthStatus>({});
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getAuthStatus();
      if (data && typeof data === "object") setStatus(data);
    } catch {
      // backend not ready yet
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchStatus();
    const interval = setInterval(() => void fetchStatus(), 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleLogin = async (service: string) => {
    setLaunching(service);
    try {
      const res = await launchLogin(service);
      if (!res.success) {
        alert(res.message);
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : t("logins.launchFailed"));
    } finally {
      setLaunching(null);
    }
  };

  if (loading) return null;

  const ids = orderServices(Object.keys(status));
  if (ids.length === 0) {
    return <p className="text-[13px] text-muted-foreground">{t("logins.none")}</p>;
  }

  const reasonFor = (id: string, name: string) => {
    if (id === "linkedin") return t("logins.linkedinReason");
    if (id === "gmail") return gmailEnabled ? t("logins.gmailReason") : t("logins.gmailOptional");
    return t("logins.genericReason", { name });
  };

  return (
    <div className="grid grid-cols-2 gap-4">
      {ids.map((id) => {
        const entry = status[id];
        const name = entry?.display_name || FALLBACK_NAMES[id] || id;
        const loggedIn = !!entry?.logged_in;
        const { nameColor, btnClass } = SERVICE_STYLES[id] || DEFAULT_STYLE;
        const optional = id === "gmail" && !gmailEnabled;
        return (
          <div
            key={id}
            data-testid={`login-card-${id}`}
            className={`bg-card rounded-xl border p-5 ${
              loggedIn ? "border-green-200" : optional ? "border-border" : "border-amber-200"
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`text-lg font-semibold ${nameColor}`}>{name}</span>
                {loggedIn ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-50 text-green-700 rounded-full text-xs font-medium">
                    <CheckCircle className="w-3 h-3" /> {t("logins.loggedIn")}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 text-amber-700 rounded-full text-xs font-medium">
                    <XCircle className="w-3 h-3" /> {t("logins.notLoggedIn")}
                  </span>
                )}
                {optional && (
                  <span className="px-2 py-0.5 bg-secondary text-muted-foreground rounded-full text-xs font-medium">
                    {t("logins.optional")}
                  </span>
                )}
              </div>
              <button
                onClick={() => void fetchStatus()}
                className="p-1 text-muted-foreground hover:text-foreground"
                title={t("logins.refresh")}
                aria-label={t("logins.refresh")}
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>

            <p className="text-xs text-muted-foreground mb-3">{reasonFor(id, name)}</p>

            {!loggedIn && (
              <button
                onClick={() => handleLogin(id)}
                disabled={launching !== null}
                className={`flex items-center gap-2 px-3 py-1.5 text-white rounded-lg text-sm font-medium disabled:opacity-50 ${btnClass}`}
              >
                {launching === id ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <LogIn className="w-3.5 h-3.5" />
                )}
                {launching === id ? t("logins.opening") : t("logins.logInTo", { name })}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
