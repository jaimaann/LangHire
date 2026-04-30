import { useState, useEffect, useCallback } from "react";
import { CheckCircle, XCircle, LogIn, Loader2, RefreshCw } from "lucide-react";
import { getAuthStatus, launchLogin } from "../lib/api";

interface ServiceStatus {
  logged_in: boolean;
}

const SERVICES = [
  {
    id: "linkedin" as const,
    name: "LinkedIn",
    reason:
      "We search and apply to jobs using your LinkedIn account. Logging in lets the agent access your profile, Easy Apply, and job listings.",
    nameColor: "text-[#0A66C2]",
    btnClass: "bg-[#0A66C2] hover:bg-[#084D93]",
  },
  {
    id: "gmail" as const,
    name: "Gmail",
    reason:
      "Some job applications require email verification (OTP codes). When Gmail is logged in, the agent can automatically read verification emails and enter the code for you.",
    nameColor: "text-red-600",
    btnClass: "bg-red-600 hover:bg-red-700",
  },
];

export default function LoginCards() {
  const [status, setStatus] = useState<Record<string, ServiceStatus>>({
    linkedin: { logged_in: false },
    gmail: { logged_in: false },
  });
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getAuthStatus();
      setStatus(data);
    } catch {
      // backend not ready yet
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const safeFetch = () => {
      fetchStatus().then(() => { if (!active) return; });
    };
    safeFetch();
    const interval = setInterval(safeFetch, 5000);
    return () => { active = false; clearInterval(interval); };
  }, [fetchStatus]);

  const handleLogin = async (service: "linkedin" | "gmail") => {
    setLaunching(service);
    try {
      const res = await launchLogin(service);
      if (!res.success) {
        alert(res.message);
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to launch browser");
    } finally {
      setLaunching(null);
    }
  };

  if (loading) return null;

  return (
    <div className="grid grid-cols-2 gap-4 mb-6">
      {SERVICES.map(({ id, name, reason, nameColor, btnClass }) => {
        const loggedIn = status[id]?.logged_in;
        return (
          <div
            key={id}
            className={`bg-white rounded-xl border p-5 ${
              loggedIn ? "border-green-200" : "border-amber-200"
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className={`text-lg font-semibold ${nameColor}`}>
                  {name}
                </span>
                {loggedIn ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-50 text-green-700 rounded-full text-xs font-medium">
                    <CheckCircle className="w-3 h-3" /> Logged in
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 text-amber-700 rounded-full text-xs font-medium">
                    <XCircle className="w-3 h-3" /> Not logged in
                  </span>
                )}
              </div>
              <button
                onClick={() => fetchStatus()}
                className="p-1 text-gray-400 hover:text-gray-600"
                title="Refresh status"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>

            <p className="text-xs text-muted-foreground mb-3">{reason}</p>

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
                {launching === id ? "Opening..." : `Log in to ${name}`}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
