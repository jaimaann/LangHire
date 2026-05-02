import { useState, useEffect, useRef } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  User,
  Cpu,
  Briefcase,
  Play,
  Brain,
  Settings,
  BookOpen,
  ScrollText,
  MessageSquare,
} from "lucide-react";
import { checkHealth } from "../../lib/api";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/guide", icon: BookOpen, label: "Guide" },
  { to: "/profile", icon: User, label: "Profile" },
  { to: "/llm", icon: Cpu, label: "LLM Settings" },
  { to: "/jobs", icon: Briefcase, label: "Jobs" },
  { to: "/apply", icon: Play, label: "Apply" },
  { to: "/memory", icon: Brain, label: "Memory" },
  { to: "/logs", icon: ScrollText, label: "Logs" },
  { to: "/settings", icon: Settings, label: "Settings" },
  { to: "/feedback", icon: MessageSquare, label: "Feedback" },
];

export default function Sidebar() {
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [buildId, setBuildId] = useState("");

  const backendOkRef = useRef(backendOk);
  backendOkRef.current = backendOk;

  useEffect(() => {
    let interval: ReturnType<typeof setTimeout> | null = null;

    const check = () => {
      checkHealth()
        .then((data) => { setBackendOk(true); setBuildId(data.build_id || ""); })
        .catch(() => setBackendOk(false));
    };
    check();

    const scheduleNext = () => {
      interval = setTimeout(() => {
        check();
        scheduleNext();
      }, backendOkRef.current ? 15000 : 2000);
    };
    scheduleNext();

    return () => { if (interval) clearTimeout(interval); };
  }, []);

  return (
    <aside className="w-60 bg-white border-r border-border flex flex-col h-screen fixed left-0 top-0">
      {/* Logo */}
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-primary rounded-xl flex items-center justify-center">
            <Briefcase className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold text-foreground tracking-tight">LangHire</h1>
            <p className="text-[11px] text-muted-foreground leading-none">AI-Powered Applications</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 space-y-0.5">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-[13px] font-semibold transition-all ${
                isActive
                  ? "bg-foreground text-white"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              }`
            }
          >
            <Icon className="w-[18px] h-[18px]" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Status */}
      <div className="px-5 py-4 border-t border-border">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            backendOk === true ? "bg-success" :
            backendOk === false ? "bg-destructive" :
            "bg-border"
          }`} />
          <span className="text-[11px] text-muted-foreground">
            {backendOk === true ? `Connected${buildId ? ` · ${buildId}` : ""}` :
             backendOk === false ? "Starting backend..." :
             "Connecting..."}
          </span>
        </div>
      </div>
    </aside>
  );
}

