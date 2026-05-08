import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Building2,
  Megaphone,
  Users,
  History,
  ClipboardCheck,
  Mailbox,
  ShieldAlert,
  CircleDot,
} from "lucide-react";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, testid: "nav-link-dashboard", end: true },
  { to: "/company", label: "Company Profile", icon: Building2, testid: "nav-link-company" },
  { to: "/campaign", label: "Campaign Builder", icon: Megaphone, testid: "nav-link-campaign" },
  { to: "/leads", label: "Leads", icon: Users, testid: "nav-link-leads" },
  { to: "/campaigns", label: "Campaigns", icon: History, testid: "nav-link-campaigns" },
  { to: "/review", label: "Review Queue", icon: ClipboardCheck, testid: "nav-link-review" },
  { to: "/mailboxes", label: "Mailboxes", icon: Mailbox, testid: "nav-link-mailboxes" },
];

export default function Layout({ children }) {
  const location = useLocation();
  const current = NAV.find(
    (item) => (item.end ? location.pathname === item.to : location.pathname.startsWith(item.to))
  );

  return (
    <div className="min-h-screen flex bg-ink-900 text-zinc-100">
      <aside className="w-64 shrink-0 border-r border-line bg-ink-900 flex flex-col">
        <div className="px-6 pt-6 pb-5 border-b border-line">
          <div className="text-[10px] tracking-overline uppercase font-semibold text-cobalt-400 mb-1">
            Outreach Cockpit
          </div>
          <div
            className="font-display text-lg font-semibold leading-tight"
            data-testid="app-brand"
          >
            Lead Email Automation
          </div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                data-testid={item.testid}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 text-sm rounded-md transition-colors ${
                    isActive
                      ? "bg-ink-700 text-white border border-line2"
                      : "text-zinc-400 hover:text-zinc-100 hover:bg-ink-800 border border-transparent"
                  }`
                }
              >
                <Icon size={16} className="shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
        <div className="p-4 border-t border-line text-[11px] text-zinc-500 leading-relaxed">
          <div className="flex items-center gap-1.5 mb-1">
            <CircleDot size={12} className="text-emerald-400" />
            <span className="font-medium text-zinc-300">Draft-first mode</span>
          </div>
          The app never sends email. Every draft requires explicit human approval.
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-line flex items-center justify-between px-6 bg-ink-900/80 backdrop-blur sticky top-0 z-10">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-xs uppercase tracking-overline text-zinc-500">
              {current ? "Workspace" : "Page"}
            </span>
            <span className="text-zinc-700">/</span>
            <span className="text-sm font-medium text-zinc-200 truncate">
              {current?.label || "Lead Email Automation"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="badge-warning"
              data-testid="safety-pill-indicator"
              title="The app does not auto-send. Drafts require human approval."
            >
              <ShieldAlert size={12} /> Human approval required
            </span>
            <span className="badge-success">No auto-send</span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1400px] mx-auto p-6 md:p-8 scroll-fade-in" key={location.pathname}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
