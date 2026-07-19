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
  ExternalLink,
  Boxes,
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
      <aside className="w-64 shrink-0 border-r border-line bg-white flex flex-col">
        <div className="px-5 pt-6 pb-5 border-b border-line">
          {/* Official Novatide logo — sourced from brand assets, never redrawn. */}
          <img
            src="/novatide-logo.png"
            alt="Novatide Consulting"
            className="h-14 w-auto mb-3"
            data-testid="app-logo"
          />
          <div className="text-[10px] tracking-overline uppercase font-semibold text-cobalt-500">
            Outreach Desk
          </div>
          <div
            className="font-display text-[17px] font-medium leading-tight text-zinc-100"
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
                  `flex items-center gap-3 px-3 py-2 text-sm rounded-sm border-l-2 transition-colors ${
                    isActive
                      ? "border-cobalt-600 bg-ink-700 text-zinc-50 font-medium"
                      : "border-transparent text-zinc-400 hover:text-zinc-100 hover:bg-ink-900"
                  }`
                }
              >
                <Icon size={16} className="shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
        <div className="px-3 py-3 border-t border-line">
          <div className="px-3 pb-1 text-[10px] uppercase tracking-overline font-semibold text-zinc-600">
            Novatide Suite
          </div>
          <a
            href="https://srppl.novatide.app"
            target="_blank"
            rel="noopener noreferrer"
            data-testid="nav-link-ims"
            className="flex items-center gap-3 px-3 py-2 text-sm rounded-sm text-zinc-400 hover:text-zinc-100 hover:bg-ink-900 transition-colors"
          >
            <Boxes size={16} className="shrink-0" />
            <span className="flex-1">SRPPL IMS</span>
            <ExternalLink size={12} className="text-zinc-600" />
          </a>
        </div>
        <div className="p-4 border-t border-line text-[11px] text-zinc-500 leading-relaxed">
          <div className="flex items-center gap-1.5 mb-1">
            <CircleDot size={12} className="text-emerald-400" />
            <span className="font-medium text-zinc-300">Approval-gated delivery</span>
          </div>
          Nothing leaves this desk without explicit human approval. Suppression is
          permanent and enforced in code.
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-line flex items-center justify-between px-6 bg-ink-900/85 backdrop-blur sticky top-0 z-10">
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
              title="Drafts require human approval. Auto-send is opt-in, capped, and compliance-gated."
            >
              <ShieldAlert size={12} /> Human approval required
            </span>
            <span className="badge-success">Suppression enforced</span>
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
