"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  BarChart3,
  Grid3x3,
  Layers,
  Scale,
  GitBranch,
  ListChecks,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/portfolio", label: "Portfolio", icon: LayoutDashboard },
  { href: "/risk", label: "Risk", icon: BarChart3 },
  { href: "/correlation", label: "Correlation", icon: Grid3x3 },
  { href: "/strategies", label: "Strategies", icon: Layers },
  { href: "/rebalance", label: "Rebalance", icon: Scale },
  { href: "/quantstats", label: "QuantStats", icon: TrendingUp },
  { href: "/montecarlo", label: "Monte Carlo", icon: GitBranch },
  { href: "/trades", label: "Trades", icon: ListChecks },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "flex flex-col h-screen bg-card border-r border-border transition-all duration-300 relative",
        collapsed ? "w-16" : "w-56"
      )}
    >
      {/* Logo Area */}
      <div className="flex items-center gap-3 p-4 border-b border-border">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-[var(--sf-green)] to-[var(--sf-cyan)] flex items-center justify-center shrink-0">
          <span className="text-background font-bold text-lg">SO</span>
        </div>
        {!collapsed && (
          <div className="flex flex-col">
            <span className="text-foreground font-semibold text-sm">SopaDeOto</span>
            <span className="text-muted-foreground text-xs">first_cohort</span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-2 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors",
                isActive
                  ? "bg-[var(--primary)]/15 text-[var(--primary)]"
                  : "text-[var(--muted-foreground)] hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <item.icon className="w-5 h-5 shrink-0" />
              {!collapsed && <span className="text-sm font-medium">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Collapse Button */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-20 w-6 h-6 rounded-full bg-card border border-border flex items-center justify-center hover:bg-accent transition-colors"
      >
        {collapsed ? (
          <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
        ) : (
          <ChevronLeft className="w-3.5 h-3.5 text-muted-foreground" />
        )}
      </button>
    </aside>
  );
}