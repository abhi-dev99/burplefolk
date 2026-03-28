import React, { useState, useEffect, useRef, useMemo } from "react";
import { motion, AnimatePresence, MotionConfig } from "framer-motion";
import {
  Database,
  FileUp,
  ListTree,
  ActivitySquare,
  ShieldCheck,
  Share2,
  BrainCircuit,
  Moon,
  Sun,
  ArrowRight,
  ArrowLeft,
  Loader2,
  Download,
  Mail,
  RefreshCw,
  Eye,
  EyeOff,
  Settings,
  ChevronRight,
  Check,
  X,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import clsx from "clsx";
import mermaid from "mermaid";
import axios from "axios";
import { toPng, toSvg } from "html-to-image";
import ERDiagram from "./components/ERDiagram";
import ErrorBoundary from "./components/ErrorBoundary";
import LandingFeatures from "./components/LandingFeatures";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

type AgentAuthState = {
  ok: boolean;
  email: string;
  idToken: string;
};

type AgentFormState = {
  firebaseApiKey: string;
  firebaseAuthDomain: string;
  firebaseProjectId: string;
  firebaseStorageBucket: string;
  firebaseLoginEmail: string;
  firebaseLoginPassword: string;
  agentEmail: string;
  gmailAppPassword: string;
  imapHost: string;
  smtpHost: string;
  smtpPort: number;
  pollSeconds: number;
  maxMessagesPerCycle: number;
  aiProvider: "ollama" | "gemini";
  ollamaEndpoint: string;
  ollamaModel: string;
  geminiApiKey: string;
  geminiModel: string;
};

type SecretFieldKey =
  | "firebaseLoginPassword"
  | "gmailAppPassword"
  | "geminiApiKey"
  | "dbPassword";

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));

const humanizeLogKey = (key: string) =>
  String(key || "")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();

const formatAgentLogMetadata = (metadata: unknown): string => {
  if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
    return "";
  }
  const obj = metadata as Record<string, unknown>;
  const entries = Object.entries(obj).slice(0, 6);
  if (entries.length === 0) {
    return "";
  }
  return entries
    .map(([key, value]) => `${humanizeLogKey(key)}: ${String(value)}`)
    .join(" | ");
};

function PasswordField({
  value,
  onChange,
  placeholder,
  visible,
  onToggle,
  className,
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder: string;
  visible: boolean;
  onToggle: () => void;
  className: string;
}) {
  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={clsx(className, "pr-10")}
      />
      <button
        type="button"
        onClick={onToggle}
        className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-100"
        aria-label={visible ? `Hide ${placeholder}` : `Show ${placeholder}`}
        title={visible ? "Hide value" : "Show value"}
      >
        {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
      </button>
    </div>
  );
}

// ------------------------------------
// UI COMPONENTS
// ------------------------------------
function SettingsMenu() {
  const [theme, setTheme] = useState<"light" | "dark" | "system">("system");
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    const isDark = document.documentElement.classList.contains("dark");
    if (isDark) setTheme("dark");
    else setTheme("light");

    // Check initial motion pref
    setReduceMotion(
      document.documentElement.classList.contains("reduced-motion"),
    );
  }, []);

  const applyTheme = (t: "light" | "dark" | "system") => {
    setTheme(t);
    const root = document.documentElement;
    root.classList.remove("dark", "hc-mode");
    if (t === "dark") root.classList.add("dark");
  };

  const toggleMotion = () => {
    setReduceMotion((r) => {
      const nr = !r;
      document.documentElement.classList.toggle("reduced-motion", nr);
      return nr;
    });
  };

  const updateFontSize = (delta: number) => {
    const root = document.documentElement;
    const current = parseFloat(getComputedStyle(root).fontSize) || 16;
    const next = Math.max(12, Math.min(24, current + delta));
    root.style.fontSize = `${next}px`;
  };

  return (
    <div className="relative group">
      <button
        className={clsx(
          "relative flex items-center justify-center p-2 rounded-full transition-all duration-500",
          "bg-white/40 dark:bg-black/40 backdrop-blur-xl border border-black/5 dark:border-white/10 shadow-sm",
          "hover:bg-white/60 dark:hover:bg-white/10 text-neutral-600 dark:text-neutral-400",
        )}
      >
        <Settings className="w-[18px] h-[18px]" />
      </button>

      {/* Main Dropdown */}
      <div className="absolute right-0 top-full mt-2 w-48 rounded-2xl bg-white/90 dark:bg-[#050505]/95 backdrop-blur-xl border border-black/10 dark:border-white/10 shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-300 z-50 py-2">
        {/* Theme Submenu Trigger */}
        <div className="relative group/theme px-4 py-2 hover:bg-black/5 dark:hover:bg-white/5 cursor-default flex items-center justify-between">
          <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300 flex items-center gap-2">
            {theme === "dark" ? (
              <Moon className="w-4 h-4" />
            ) : theme === "light" ? (
              <Sun className="w-4 h-4" />
            ) : (
              <ActivitySquare className="w-4 h-4" />
            )}{" "}
            Theme
          </span>
          <ChevronRight className="w-4 h-4 text-neutral-400" />

          {/* Nested Theme Options */}
          <div className="absolute right-[105%] top-0 w-40 rounded-xl bg-white/90 dark:bg-[#050505]/95 backdrop-blur-xl border border-black/10 dark:border-white/10 shadow-xl opacity-0 invisible group-hover/theme:opacity-100 group-hover/theme:visible transition-all duration-200 py-1">
            {(["light", "dark", "system"] as const).map((t) => (
              <button
                key={t}
                onClick={() => applyTheme(t)}
                className="w-full text-left px-4 py-2 text-sm text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 capitalize flex items-center justify-between"
              >
                {t.replace("-", " ")}
                {theme === t && (
                  <Check className="w-3 h-3 text-[#0059B5] dark:text-[#60A5FA]" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Accessibility Toggles */}
        <div className="border-t border-black/5 dark:border-white/5 my-1" />
        <button
          onClick={toggleMotion}
          className="w-full text-left px-4 py-2 hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer flex items-center justify-between"
        >
          <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300 flex items-center gap-2">
            Reduced Motion
          </span>
          {reduceMotion && (
            <Check className="w-3 h-3 text-[#0059B5] dark:text-[#60A5FA]" />
          )}
        </button>
        <div className="px-4 py-2 flex items-center justify-between">
          <span className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
            Font Size
          </span>
          <div className="flex items-center gap-1 bg-black/5 dark:bg-white/5 rounded-md p-0.5">
            <button
              onClick={() => updateFontSize(-1)}
              className="px-2 py-0.5 hover:bg-white dark:hover:bg-black rounded text-xs font-semibold text-neutral-600 dark:text-neutral-400"
            >
              A-
            </button>
            <button
              onClick={() => updateFontSize(1)}
              className="px-2 py-0.5 hover:bg-white dark:hover:bg-black rounded text-sm font-bold text-neutral-600 dark:text-neutral-400"
            >
              A+
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function TopNav({
  activeTab,
  setActiveTab,
  showAnalysisNav,
  children,
}: {
  activeTab?: string;
  setActiveTab?: (t: string) => void;
  showAnalysisNav: boolean;
  children?: React.ReactNode;
}) {
  const navItems = [
    { id: "overview", label: "Overview" },
    { id: "schema", label: "Schema" },
    { id: "quality", label: "Quality" },
    { id: "er", label: "ER Diagram" },
    { id: "dictionary", label: "Dictionary" },
    { id: "ai", label: "AI Review" },
    { id: "exports", label: "Exports" },
  ];

  return (
    <nav className="fixed top-4 left-1/2 -translate-x-1/2 z-50 w-[95%] max-w-5xl rounded-[2rem] bg-white/60 dark:bg-black/40 backdrop-blur-3xl border border-white/40 dark:border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.04)] dark:shadow-[0_8px_32px_rgba(0,0,0,0.2)] print-hidden">
      <div className="flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-3 min-w-fit">
          <span className="font-medium text-[22px] tracking-tight text-neutral-900 dark:text-neutral-100 font-inter lowercase whitespace-nowrap">
            <span className="font-bold">nexus</span> intelligence.
          </span>
        </div>

        {showAnalysisNav && setActiveTab && (
          <div className="hidden md:flex items-center px-3">
            <div>
              <div className="nav-scrollbar-none flex items-center gap-1 bg-black/5 dark:bg-white/5 p-1 rounded-full flex-nowrap overflow-x-auto scroll-smooth">
                {navItems.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={clsx(
                      "px-3 py-1.5 rounded-full text-[13px] font-medium transition-all duration-300 whitespace-nowrap",
                      activeTab === item.id
                        ? "bg-white dark:bg-neutral-800 text-black dark:text-white shadow-sm"
                        : "text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200",
                    )}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          {children}
        </div>
      </div>
    </nav>
  );
}

// ------------------------------------
// FUNCTIONAL VIEWS
// ------------------------------------
const highlightText = (text: string) => {
  if (!text) return text;
  const highlighted = text
    .replace(
      /([a-zA-Z0-9_]+(?=\s*\())/g,
      '<span class="text-[#0059B5] dark:text-[#60A5FA] font-medium">$1</span>',
    )
    .replace(
      /(\d+(?:\.\d+)?%)/g,
      '<span class="bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded-md font-medium text-sm">$1</span>',
    )
    .replace(
      /(candidate foreign-key links|Largest table|issues)/gi,
      '<span class="text-rose-600 dark:text-rose-400 font-medium">$1</span>',
    );
  return <span dangerouslySetInnerHTML={{ __html: highlighted }} />;
};

const escapeHtml = (value: string) =>
  String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const formatInlineMarkdown = (line: string) => {
  return escapeHtml(line)
    .replace(
      /\*\*(.*?)\*\*/g,
      '<strong class="font-medium text-neutral-900 dark:text-white">$1</strong>',
    )
    .replace(
      /`([^`]+)`/g,
      '<code class="bg-black/5 dark:bg-white/10 px-1.5 py-0.5 rounded text-sm font-mono text-purple-600 dark:text-purple-300">$1</code>',
    );
};

const formatAiBriefToHtml = (raw: string) => {
  const text = String(raw || "").replace(/\r\n/g, "\n");
  const lines = text.split("\n");
  const out: string[] = [];

  let i = 0;
  while (i < lines.length) {
    const line = lines[i] || "";
    const trimmed = line.trim();

    if (!trimmed) {
      i += 1;
      continue;
    }

    // Markdown pipe table block.
    if (
      trimmed.includes("|") &&
      i + 1 < lines.length &&
      /^\s*\|?\s*[-:]+/.test(lines[i + 1] || "")
    ) {
      const tableLines: string[] = [line, lines[i + 1]];
      i += 2;
      while (
        i < lines.length &&
        (lines[i] || "").includes("|") &&
        (lines[i] || "").trim()
      ) {
        tableLines.push(lines[i]);
        i += 1;
      }

      const cells = (row: string) =>
        row
          .trim()
          .replace(/^\|/, "")
          .replace(/\|$/, "")
          .split("|")
          .map((c) => formatInlineMarkdown(c.trim()));

      const headerCells = cells(tableLines[0]);
      const bodyRows = tableLines.slice(2).map((r) => cells(r));

      out.push(
        '<div class="overflow-x-auto my-4"><table class="min-w-full border border-black/10 dark:border-white/10 rounded-xl overflow-hidden">',
      );
      out.push('<thead class="bg-black/5 dark:bg-white/10"><tr>');
      headerCells.forEach((h) =>
        out.push(
          `<th class="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider">${h}</th>`,
        ),
      );
      out.push("</tr></thead><tbody>");
      bodyRows.forEach((row) => {
        out.push('<tr class="border-t border-black/5 dark:border-white/10">');
        row.forEach((c) => out.push(`<td class="px-3 py-2 text-sm">${c}</td>`));
        out.push("</tr>");
      });
      out.push("</tbody></table></div>");
      continue;
    }

    if (/^###\s+/.test(trimmed)) {
      out.push(
        `<h3 class="text-xl font-medium text-purple-600 dark:text-purple-400 mb-2 mt-4">${formatInlineMarkdown(trimmed.replace(/^###\s+/, ""))}</h3>`,
      );
      i += 1;
      continue;
    }
    if (/^##\s+/.test(trimmed)) {
      out.push(
        `<h3 class="text-xl font-medium text-purple-600 dark:text-purple-400 mb-2 mt-4">${formatInlineMarkdown(trimmed.replace(/^##\s+/, ""))}</h3>`,
      );
      i += 1;
      continue;
    }
    if (/^#\s+/.test(trimmed)) {
      out.push(
        `<h3 class="text-xl font-medium text-purple-600 dark:text-purple-400 mb-2 mt-4">${formatInlineMarkdown(trimmed.replace(/^#\s+/, ""))}</h3>`,
      );
      i += 1;
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test((lines[i] || "").trim())) {
        items.push((lines[i] || "").trim().replace(/^[-*]\s+/, ""));
        i += 1;
      }
      out.push('<ul class="list-disc list-inside my-2 space-y-1">');
      items.forEach((item) =>
        out.push(`<li>${formatInlineMarkdown(item)}</li>`),
      );
      out.push("</ul>");
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test((lines[i] || "").trim())) {
        items.push((lines[i] || "").trim().replace(/^\d+\.\s+/, ""));
        i += 1;
      }
      out.push('<ol class="list-decimal list-inside my-2 space-y-1">');
      items.forEach((item) =>
        out.push(`<li>${formatInlineMarkdown(item)}</li>`),
      );
      out.push("</ol>");
      continue;
    }

    out.push(`<p class="my-2">${formatInlineMarkdown(trimmed)}</p>`);
    i += 1;
  }

  return out.join("");
};

function TableNavigatorFAB({
  activeTab,
  tables,
  analysisData,
  sortMethod,
  setSortMethod,
}: {
  activeTab: string;
  tables: string[];
  analysisData: any;
  sortMethod: "asc" | "desc" | "A-Z" | "Z-A";
  setSortMethod: (v: "asc" | "desc" | "A-Z" | "Z-A") => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const closeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  if (
    !["schema", "quality", "dictionary"].includes(activeTab) ||
    !tables.length
  )
    return null;

  let displayTables = [...tables];
  if (activeTab === "quality") {
    const getScore = (t: string) => {
      const p = analysisData?.analysis?.table_profiles?.find(
        (x: any) => x.table === t,
      );
      return p?.quality_score || 0;
    };
    if (sortMethod === "desc")
      displayTables.sort((a, b) => getScore(b) - getScore(a));
    else if (sortMethod === "asc")
      displayTables.sort((a, b) => getScore(a) - getScore(b));
    else if (sortMethod === "A-Z")
      displayTables.sort((a, b) => a.localeCompare(b));
    else if (sortMethod === "Z-A")
      displayTables.sort((a, b) => b.localeCompare(a));
  } else {
    if (sortMethod === "A-Z" || sortMethod === "desc" || sortMethod === "asc")
      displayTables.sort((a, b) => a.localeCompare(b));
    else if (sortMethod === "Z-A")
      displayTables.sort((a, b) => b.localeCompare(a));
  }

  const handleMouseEnter = () => {
    if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current);
    setIsOpen(true);
  };

  const handleMouseLeave = () => {
    closeTimeoutRef.current = setTimeout(() => setIsOpen(false), 1000);
  };

  return (
    <div
      className="fixed bottom-6 right-6 z-[60]"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* Popover */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.8, borderRadius: "3rem" }}
            animate={{ opacity: 1, scale: 1, borderRadius: "1rem" }}
            exit={{ opacity: 0, scale: 0.8, borderRadius: "3rem" }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            style={{ transformOrigin: "bottom right" }}
            className="absolute bottom-0 right-0 w-auto min-w-[240px] max-w-[320px] bg-white/95 dark:bg-[#0b1220]/95 backdrop-blur-xl border border-black/10 dark:border-white/10 shadow-2xl overflow-hidden flex flex-col hc-mode:bg-black hc-mode:border-white"
          >
            {/* Header */}
            <div className="p-4 border-b border-black/5 dark:border-white/5 flex flex-col gap-3">
              <div className="flex justify-between items-center">
                <h3 className="font-semibold text-neutral-800 dark:text-neutral-100 hc-mode:text-white flex items-center gap-2">
                  <ListTree className="w-4 h-4 text-[#0059B5] dark:text-[#60A5FA]" />
                  Navigate Tables
                </h3>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1 rounded-full text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="flex bg-black/5 dark:bg-white/5 p-1 rounded-lg gap-1">
                <button
                  onClick={() => setSortMethod("A-Z")}
                  className={clsx(
                    "flex-1 text-xs py-1.5 rounded-md transition-all font-medium whitespace-nowrap px-2",
                    sortMethod === "A-Z"
                      ? "bg-white dark:bg-[#2a3441] shadow-sm text-neutral-900 dark:text-white"
                      : "text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200",
                  )}
                >
                  A-Z
                </button>
                <button
                  onClick={() => setSortMethod("Z-A")}
                  className={clsx(
                    "flex-1 text-xs py-1.5 rounded-md transition-all font-medium whitespace-nowrap px-2",
                    sortMethod === "Z-A"
                      ? "bg-white dark:bg-[#2a3441] shadow-sm text-neutral-900 dark:text-white"
                      : "text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200",
                  )}
                >
                  Z-A
                </button>
                {activeTab === "quality" && (
                  <>
                    <button
                      onClick={() => setSortMethod("desc")}
                      className={clsx(
                        "flex-1 text-xs py-1.5 rounded-md transition-all font-medium whitespace-nowrap px-2 flex items-center justify-center gap-1",
                        sortMethod === "desc"
                          ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400"
                          : "text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200",
                      )}
                    >
                      Score <ArrowDown className="w-3 h-3" />
                    </button>
                    <button
                      onClick={() => setSortMethod("asc")}
                      className={clsx(
                        "flex-1 text-xs py-1.5 rounded-md transition-all font-medium whitespace-nowrap px-2 flex items-center justify-center gap-1",
                        sortMethod === "asc"
                          ? "bg-rose-500/20 text-rose-700 dark:text-rose-400"
                          : "text-neutral-500 hover:text-neutral-700 dark:text-neutral-400 dark:hover:text-neutral-200",
                      )}
                    >
                      Score <ArrowUp className="w-3 h-3" />
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Scrollable List */}
            <div className="max-h-[60vh] min-h-[10vh] overflow-y-auto p-2">
              {displayTables.map((tName) => {
                const score =
                  activeTab === "quality"
                    ? analysisData?.analysis?.table_profiles?.find(
                        (x: any) => x.table === tName,
                      )?.quality_score
                    : null;
                return (
                  <button
                    key={`nav-${tName}`}
                    onClick={() => {
                      setIsOpen(false);
                      const idMap: Record<string, string> = {
                        schema: "schema-table-",
                        quality: "quality-table-",
                        dictionary: "dict-table-",
                      };
                      document
                        .getElementById(`${idMap[activeTab]}${tName}`)
                        ?.scrollIntoView({
                          behavior: "smooth",
                          block: "start",
                        });
                    }}
                    className="w-full text-left px-3 py-2.5 rounded-xl hover:bg-black/5 dark:hover:bg-white/5 hc-mode:hover:bg-white/20 transition-colors flex items-center justify-between group"
                  >
                    <div className="flex items-center gap-2">
                      <ChevronRight className="w-4 h-4 text-black/20 dark:text-white/20 group-hover:text-black/50 dark:group-hover:text-white/50 hc-mode:text-gray-500 transition-colors shrink-0" />
                      <span className="text-sm font-medium text-neutral-700 dark:text-neutral-200 hc-mode:text-white tracking-wide truncate pr-2">
                        {tName}
                      </span>
                    </div>
                    {score !== null && score !== undefined && (
                      <span
                        className={clsx(
                          "shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-md",
                          score > 80
                            ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                            : score > 60
                              ? "bg-amber-500/10 text-amber-700 dark:text-amber-400"
                              : "bg-rose-500/10 text-rose-700 dark:text-rose-400",
                        )}
                      >
                        {Math.round(score)}%
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          "p-4 rounded-full shadow-2xl backdrop-blur-xl border border-black/10 dark:border-white/10 transition-all duration-300 flex items-center justify-center hc-mode:bg-white hc-mode:text-black absolute bottom-0 right-0 z-0",
          isOpen
            ? "opacity-0 scale-75 pointer-events-none"
            : "opacity-100 scale-100 bg-white/80 dark:bg-[#0b1220]/80 text-[#0059B5] dark:text-[#60A5FA] hover:scale-105 active:scale-95 hover:shadow-[#0059B5]/20 dark:hover:shadow-[#60A5FA]/20",
        )}
      >
        <ListTree className="w-6 h-6" />
      </button>
    </div>
  );
}

function DataView({
  activeTab,
  analysisData,
  processedRowLimit,
}: {
  activeTab: string;
  analysisData: any;
  processedRowLimit: number;
}) {
  const mermaidRef = useRef<HTMLDivElement>(null);
  const erDiagramRef = useRef<HTMLDivElement>(null);
  const [copyStatus, setCopyStatus] = useState<string>("");
  const [histTooltip, setHistTooltip] = useState<{
    x: number;
    y: number;
    min: number;
    max: number;
    count: number;
  } | null>(null);

  const renderRowTable = (row: any, color: "emerald" | "rose") => {
    if (!row)
      return (
        <span className={`text-${color}-500 italic`}>No data available</span>
      );
    const entries = Object.entries(row);
    if (entries.length === 0)
      return (
        <span className={`text-${color}-500 italic`}>No data available</span>
      );
    return (
      <div className="overflow-x-auto w-full">
        <table className="w-full text-left text-[11px] font-mono whitespace-nowrap">
          <thead>
            <tr className={`border-b border-${color}-500/20`}>
              {entries.map(([k]) => (
                <th
                  key={k}
                  className={`p-2 text-${color}-700 dark:text-${color}-300 font-medium`}
                >
                  {k}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className={`divide-x divide-${color}-500/10`}>
              {entries.map(([_, v], i) => (
                <td
                  key={i}
                  className={`p-2 text-${color}-900 dark:text-${color}-100`}
                >
                  {String(v)}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    );
  };
  const [dictSearch, setDictSearch] = useState("");
  const [aiPrompt, setAiPrompt] = useState(
    "Generate a comprehensive executive brief addressing data completeness and consistency...",
  );
  const [isGeneratingAi, setIsGeneratingAi] = useState(false);
  const [aiResponse, setAiResponse] = useState<string | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiOrchestration, setAiOrchestration] = useState<any | null>(null);
  const [aiProvider, setAiProvider] = useState<"gemini" | "ollama">("gemini");
  const [aiGeminiApiKey, setAiGeminiApiKey] = useState("");
  const [aiGeminiModel, setAiGeminiModel] = useState("gemini-2.0-flash");
  const [aiOllamaEndpoint, setAiOllamaEndpoint] = useState(
    "http://localhost:11434",
  );
  const [aiOllamaModel, setAiOllamaModel] = useState("llama3:latest");
  const [aiOllamaModels, setAiOllamaModels] = useState<string[]>([]);
  const [aiModelLoading, setAiModelLoading] = useState(false);

  const tables = useMemo(
    () =>
      analysisData?.analysis?.table_profiles
        ? analysisData.analysis.table_profiles.map((p: any) => p.table)
        : [],
    [analysisData],
  );
  const [editorTarget, setEditorTarget] = useState<string | null>(null);
  const currentEditorTarget = editorTarget || tables[0] || "";
  const [tableMenuSort, setTableMenuSort] = useState<
    "A-Z" | "Z-A" | "asc" | "desc"
  >("A-Z");

  const handleAiAction = async () => {
    if (!analysisData?.analysis) {
      setAiError("Analyze a dataset first before generating an AI brief.");
      return;
    }

    setIsGeneratingAi(true);
    setAiError(null);
    try {
      const fallbackProvider = aiProvider === "gemini" ? "ollama" : "gemini";
      const timeoutSeconds = aiProvider === "ollama" ? 180 : 90;
      const res = await axios.post(`${API_BASE}/ai/brief`, {
        analysis: analysisData.analysis,
        prompt: aiPrompt,
        provider_preference: aiProvider,
        fallback_provider: fallbackProvider,
        gemini_api_key: aiGeminiApiKey,
        gemini_model: aiGeminiModel,
        ollama_endpoint: aiOllamaEndpoint,
        ollama_model: aiOllamaModel,
        timeout_seconds: timeoutSeconds,
      });
      const nextBrief = String(res.data?.ai_brief || "").trim();
      setAiResponse(nextBrief || null);
      setAiOrchestration(res.data?.orchestration || null);
    } catch (err: any) {
      const message = String(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to generate AI brief.",
      );
      setAiError(message);
    } finally {
      setIsGeneratingAi(false);
    }
  };

  const refreshAiOllamaModels = async (endpoint: string) => {
    setAiModelLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/agent/ollama-models`, {
        params: { endpoint },
      });
      const models = Array.isArray(res.data?.models)
        ? (res.data.models as string[])
        : [];
      setAiOllamaModels(models);
      if (models.length > 0 && !models.includes(aiOllamaModel)) {
        setAiOllamaModel(models[0]);
      }
    } catch {
      setAiOllamaModels([]);
    } finally {
      setAiModelLoading(false);
    }
  };

  useEffect(() => {
    const loadAiDefaults = async () => {
      try {
        const res = await axios.get(`${API_BASE}/agent/defaults`);
        const defaults = res.data || {};
        const provider = defaults.aiProvider === "ollama" ? "ollama" : "gemini";
        setAiProvider(provider);
        setAiGeminiApiKey(String(defaults.geminiApiKey || ""));
        setAiGeminiModel(String(defaults.geminiModel || "gemini-2.0-flash"));
        setAiOllamaEndpoint(
          String(defaults.ollamaEndpoint || "http://localhost:11434"),
        );
        const models = Array.isArray(defaults.ollamaModels)
          ? (defaults.ollamaModels as string[])
          : [];
        setAiOllamaModels(models);
        setAiOllamaModel(
          String(defaults.ollamaModel || models[0] || "llama3:latest"),
        );
      } catch {
        // Keep local defaults.
      }
    };
    loadAiDefaults();
  }, []);

  useEffect(() => {
    if (activeTab === "er" && analysisData?.er_diagram && mermaidRef.current) {
      mermaid.initialize({
        startOnLoad: false,
        theme: "base",
        themeVariables: {
          fontFamily: "Inter, sans-serif",
          background: "transparent",
          primaryColor: document.documentElement.classList.contains("dark")
            ? "#1a1a1a"
            : "#fcfcfc",
          primaryBorderColor: document.documentElement.classList.contains(
            "dark",
          )
            ? "#333"
            : "#e5e5e5",
          lineColor: document.documentElement.classList.contains("dark")
            ? "#666"
            : "#bfbfbf",
          textColor: document.documentElement.classList.contains("dark")
            ? "#f5f5f5"
            : "#111",
          nodeBorder: document.documentElement.classList.contains("dark")
            ? "#444"
            : "#ddd",
        },
        securityLevel: "loose",
      });
      mermaid
        .render("mermaid-svg", analysisData.er_diagram)
        .then((result) => {
          if (mermaidRef.current) {
            mermaidRef.current.innerHTML = result.svg;
          }
        })
        .catch((err) => console.error("Mermaid error", err));
    }
  }, [activeTab, analysisData]);

  const downloadErAsPng = async () => {
    if (!erDiagramRef.current) return;
    try {
      const dataUrl = await toPng(erDiagramRef.current, {
        cacheBust: true,
        pixelRatio: 2,
      });
      const link = document.createElement("a");
      link.href = dataUrl;
      link.download = "nexus_er_diagram.png";
      link.click();
    } catch (error) {
      console.error("Failed to export PNG", error);
      alert("Could not export PNG. Please try again.");
    }
  };

  const downloadErAsSvg = async () => {
    if (!erDiagramRef.current) return;
    try {
      const dataUrl = await toSvg(erDiagramRef.current, { cacheBust: true });
      const link = document.createElement("a");
      link.href = dataUrl;
      link.download = "nexus_er_diagram.svg";
      link.click();
    } catch (error) {
      console.error("Failed to export SVG", error);
      alert("Could not export SVG. Please try again.");
    }
  };

  const copyMermaidCode = async () => {
    const code = String(analysisData?.er_diagram || "").trim();
    if (!code) {
      setCopyStatus("No Mermaid code available yet.");
      return;
    }
    try {
      await navigator.clipboard.writeText(code);
      setCopyStatus("Mermaid code copied.");
      setTimeout(() => setCopyStatus(""), 1800);
    } catch {
      setCopyStatus("Clipboard blocked by browser.");
      setTimeout(() => setCopyStatus(""), 1800);
    }
  };

  const GlassCard = ({
    children,
    className = "",
    id,
  }: {
    children: React.ReactNode;
    className?: string;
    id?: string;
  }) => (
    <div
      id={id}
      className={clsx(
        "bg-white/40 dark:bg-black/20 backdrop-blur-xl border border-white/40 dark:border-white/5 rounded-[2rem] shadow-[0_8px_30px_rgba(0,0,0,0.02)] overflow-hidden",
        className,
      )}
    >
      {children}
    </div>
  );

  const overviewTables = analysisData?.analysis?.table_profiles || [];
  const avgQuality = analysisData?.analysis?.avg_quality_score || 0;
  const relationships = Array.isArray(analysisData?.analysis?.relationships)
    ? analysisData.analysis.relationships
    : [];

  const storageEstimateBytes = useMemo(() => {
    const samples = analysisData?.sample_tables || {};
    return overviewTables.reduce((acc: number, profile: any) => {
      const tableName = String(profile?.table || "");
      const estimatedRows = Number(profile?.estimated_total_rows || 0);
      const sampleRows = Array.isArray(samples?.[tableName])
        ? samples[tableName]
        : [];
      const sampleBytes =
        sampleRows.length > 0
          ? sampleRows.reduce(
              (s: number, r: any) => s + JSON.stringify(r || {}).length,
              0,
            )
          : 0;
      const avgRowBytes =
        sampleRows.length > 0
          ? Math.max(32, Math.round(sampleBytes / sampleRows.length))
          : Math.max(32, Number(profile?.column_count || 4) * 16);
      return acc + estimatedRows * avgRowBytes;
    }, 0);
  }, [overviewTables, analysisData]);

  const storageEstimateLabel = useMemo(() => {
    if (storageEstimateBytes >= 1024 * 1024) {
      return `${(storageEstimateBytes / (1024 * 1024)).toFixed(2)} MB`;
    }
    if (storageEstimateBytes >= 1024) {
      return `${Math.max(1, Math.round(storageEstimateBytes / 1024))} KB`;
    }
    return `${Math.max(1, storageEstimateBytes)} B`;
  }, [storageEstimateBytes]);

  const orphanTableCount = useMemo(() => {
    if (overviewTables.length === 0) {
      return 0;
    }
    const connected = new Set<string>();
    relationships.forEach((r: any) => {
      const child = String(r?.child_table || "").trim();
      const parent = String(r?.parent_table || "").trim();
      if (child) connected.add(child);
      if (parent) connected.add(parent);
    });
    return overviewTables.filter(
      (t: any) => !connected.has(String(t?.table || "")),
    ).length;
  }, [overviewTables, relationships]);
  const semanticLayer = analysisData?.analysis?.semantic_layer || {};
  const semanticSuggestions =
    semanticLayer?.mapping_suggestions?.suggestions || [];
  const semanticMetrics = semanticLayer?.metrics || [];
  const semanticConstraints = semanticLayer?.constraints || [];
  const semanticEntities = semanticLayer?.table_entities || [];
  const semanticAmbiguities = semanticLayer?.ambiguities || [];

  return (
    <div className="w-full pb-20">
      {/* OVERVIEW */}
      <div
        className={clsx(
          "animate-in fade-in slide-in-from-bottom-4 duration-700 w-full mt-24 print:mt-0 print:break-after-page print:block",
          activeTab !== "overview" && "hidden",
        )}
      >
        <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">
          System <span className="font-medium text-[#0059B5]">Overview</span>
        </h2>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-8">
          <GlassCard className="p-8">
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-2">
              Total Tables
            </h3>
            <div className="text-5xl font-light text-neutral-900 dark:text-neutral-100">
              {tables.length}
            </div>
          </GlassCard>
          <GlassCard className="p-8">
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-2">
              Storage (Est)
            </h3>
            <div className="text-5xl font-light text-neutral-900 dark:text-neutral-100">
              {storageEstimateLabel}
            </div>
          </GlassCard>
          <GlassCard className="p-8">
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-2">
              Avg Quality
            </h3>
            <div className="text-5xl font-light text-[#0059B5] dark:text-[#60A5FA]">
              {avgQuality}
              <span className="text-2xl">%</span>
            </div>
          </GlassCard>
          <GlassCard className="p-8">
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-2">
              Relationships
            </h3>
            <div className="text-5xl font-light text-neutral-900 dark:text-neutral-100">
              {analysisData?.analysis?.relationships?.length || 0}
            </div>
          </GlassCard>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
          <GlassCard className="p-8">
            <h3 className="text-lg font-light text-neutral-900 dark:text-white mb-4">
              Risk Snapshot
            </h3>
            <div className="overflow-x-auto rounded-2xl border border-black/10 dark:border-white/10">
              <table className="w-full text-left text-sm">
                <thead className="bg-black/5 dark:bg-white/10">
                  <tr>
                    <th className="px-4 py-3">table</th>
                    <th className="px-4 py-3 text-right">quality_score</th>
                    <th className="px-4 py-3 text-right">issues</th>
                    <th className="px-4 py-3 text-right">rows</th>
                    <th className="px-4 py-3 text-right">columns</th>
                  </tr>
                </thead>
                <tbody>
                  {[...overviewTables]
                    .sort(
                      (a: any, b: any) =>
                        Number(a?.quality_score || 0) -
                        Number(b?.quality_score || 0),
                    )
                    .slice(0, 6)
                    .map((t: any) => (
                      <tr
                        key={String(t?.table || "")}
                        className="border-t border-black/5 dark:border-white/10"
                      >
                        <td className="px-4 py-2.5 font-medium">
                          {String(t?.table || "")}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {Number(t?.quality_score || 0).toFixed(2)}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {Array.isArray(t?.issues) ? t.issues.length : 0}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {Number(t?.estimated_total_rows || 0)}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {Number(t?.column_count || 0)}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </GlassCard>

          <GlassCard className="p-8">
            <h3 className="text-lg font-light text-neutral-900 dark:text-white mb-4">
              Business Context
            </h3>
            <p className="text-neutral-600 dark:text-neutral-300 font-light leading-relaxed whitespace-pre-wrap text-base">
              {highlightText(
                analysisData?.analysis?.business_context ||
                  "No context generated.",
              )}
            </p>
          </GlassCard>

          <GlassCard className="p-8">
            <h3 className="text-lg font-light text-neutral-900 dark:text-white mb-4">
              Schema Drift & Governance
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between text-sm border-b border-black/5 dark:border-white/5 pb-2">
                <span className="text-neutral-600 dark:text-neutral-300 font-light">
                  Missing `updated_at`
                </span>
                <span className="text-rose-500 font-medium">
                  {
                    tables.filter(
                      (t: any) =>
                        !t.column_profiles?.some((c: any) =>
                          String(c.column).includes("updated"),
                        ),
                    ).length
                  }{" "}
                  tables
                </span>
              </div>
              <div className="flex items-center justify-between text-sm border-b border-black/5 dark:border-white/5 pb-2">
                <span className="text-neutral-600 dark:text-neutral-300 font-light">
                  Missing `created_at`
                </span>
                <span className="text-rose-500 font-medium">
                  {
                    tables.filter(
                      (t: any) =>
                        !t.column_profiles?.some((c: any) =>
                          String(c.column).includes("created"),
                        ),
                    ).length
                  }{" "}
                  tables
                </span>
              </div>
              <div className="flex items-center justify-between text-sm pb-2">
                <span className="text-neutral-600 dark:text-neutral-300 font-light">
                  Orphan Tables (No FKs)
                </span>
                <span className="text-amber-500 font-medium">
                  {orphanTableCount} tables
                </span>
              </div>
            </div>
          </GlassCard>
        </div>
      </div>
      <TableNavigatorFAB
        activeTab={activeTab}
        tables={tables}
        analysisData={analysisData}
        sortMethod={tableMenuSort}
        setSortMethod={setTableMenuSort}
      />

      {/* SCHEMA */}
      <div
        className={clsx(
          "w-full mt-24 print:mt-10 print:break-after-page print:block",
          activeTab !== "schema" && "hidden",
        )}
      >
        {(() => {
          const profiles = overviewTables;
          return (
            <div className="w-full">
              <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">
                Data <span className="font-medium">Schema</span>
              </h2>

              {profiles.length === 0 ? (
                <div className="text-neutral-400 italic p-6">
                  No schema data identified.
                </div>
              ) : (
                <>
                  <div className="grid gap-12 mt-8">
                    {profiles.map((profile: any) => (
                      <GlassCard
                        key={profile.table}
                        className="scroll-mt-32"
                        id={`schema-table-${profile.table}`}
                      >
                        <div className="px-8 py-6 flex items-center justify-between border-b border-black/5 dark:border-white/5 bg-white/20 dark:bg-black/20">
                          <h3 className="text-2xl font-light tracking-wide text-neutral-900 dark:text-white flex items-center gap-4">
                            {profile.table}
                            <span className="text-xs font-medium bg-neutral-100 dark:bg-neutral-800/60 px-3 py-1 rounded-full text-neutral-500">
                              {profile.estimated_total_rows || 0} rows
                            </span>
                          </h3>
                        </div>
                        <div className="overflow-x-auto p-4 max-h-[500px]">
                          <table className="w-full text-left text-sm text-neutral-600 dark:text-neutral-300">
                            <thead>
                              <tr>
                                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400">
                                  Column
                                </th>
                                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400">
                                  Type
                                </th>
                                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400">
                                  Role
                                </th>
                                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400">
                                  Null %
                                </th>
                                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400">
                                  Unique %
                                </th>
                                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400 w-48 hidden md:table-cell">
                                  Distribution
                                </th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-black/5 dark:divide-white/5">
                              {profile.column_profiles?.map((col: any) => (
                                <tr
                                  key={col.column}
                                  className="hover:bg-white/40 dark:hover:bg-white/5 transition-colors"
                                >
                                  <td className="px-6 py-4 font-medium text-neutral-900 dark:text-neutral-100">
                                    {col.column}
                                  </td>
                                  <td className="px-6 py-4">
                                    <span className="font-mono text-xs text-[#0059B5] dark:text-[#60A5FA] bg-[#0059B5]/10 dark:bg-[#60A5FA]/10 px-2 py-1 rounded-md">
                                      {col.sample_dtype}
                                    </span>
                                  </td>
                                  <td className="px-6 py-4 font-light">
                                    {col.semantic_role || "-"}
                                  </td>
                                  <td className="px-6 py-4 font-light">
                                    {col.null_percent}%
                                  </td>
                                  <td className="px-6 py-4 font-light">
                                    {col.unique_percent}%
                                  </td>
                                  <td className="px-6 py-4 hidden md:table-cell">
                                    {[
                                      "int",
                                      "float",
                                      "number",
                                      "decimal",
                                      "double",
                                    ].some((t) =>
                                      String(col.sample_dtype || "")
                                        .toLowerCase()
                                        .includes(t),
                                    ) ? (
                                      <div
                                        className="group w-full flex items-end gap-[1px] h-8 cursor-crosshair relative border-b border-neutral-300 dark:border-neutral-700"
                                        aria-label="Distribution Histogram"
                                      >
                                        {col.histogram &&
                                        Array.isArray(col.histogram) &&
                                        col.histogram.length > 0 ? (
                                          col.histogram.map(
                                            (bin: any, i: number) => {
                                              const maxCount = Math.max(
                                                ...col.histogram.map(
                                                  (b: any) => b.count,
                                                ),
                                                1,
                                              );
                                              const val = Math.max(
                                                5,
                                                (bin.count / maxCount) * 100,
                                              );
                                              return (
                                                <div
                                                  key={i}
                                                  className="flex-1 rounded-t-[1px] bg-[#0059B5]/40 hover:bg-[#0059B5] dark:bg-[#60A5FA]/40 dark:hover:bg-[#60A5FA] transition-all relative group/bar"
                                                  style={{ height: `${val}%` }}
                                                  onMouseEnter={(e) => {
                                                    const rect =
                                                      e.currentTarget.getBoundingClientRect();
                                                    setHistTooltip({
                                                      x:
                                                        rect.left +
                                                        rect.width / 2,
                                                      y: rect.top - 8,
                                                      min: Math.floor(
                                                        bin["min Bound"],
                                                      ),
                                                      max: Math.floor(
                                                        bin["max Bound"],
                                                      ),
                                                      count: bin.count,
                                                    });
                                                  }}
                                                  onMouseLeave={() =>
                                                    setHistTooltip(null)
                                                  }
                                                />
                                              );
                                            },
                                          )
                                        ) : (
                                          <span className="text-xs text-neutral-400 font-medium my-auto mx-auto tracking-wide">
                                            NO DATA
                                          </span>
                                        )}
                                      </div>
                                    ) : (
                                      <span className="text-neutral-400 font-light text-[10px] uppercase tracking-wider">
                                        Categorical
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </GlassCard>
                    ))}
                  </div>
                </>
              )}
            </div>
          );
        })()}
      </div>

      {/* QUALITY */}
      <div
        className={clsx(
          "w-full mt-24 print:mt-10 print:break-after-page print:block",
          activeTab !== "quality" && "hidden",
        )}
      >
        {(() => {
          const sortedProfiles = [...overviewTables].sort((a: any, b: any) => {
            if (tableMenuSort === "desc")
              return (b.quality_score || 0) - (a.quality_score || 0);
            if (tableMenuSort === "asc")
              return (a.quality_score || 0) - (b.quality_score || 0);
            if (tableMenuSort === "Z-A") return b.table.localeCompare(a.table);
            return a.table.localeCompare(b.table);
          });
          return (
            <div className="w-full">
              <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">
                Data{" "}
                <span className="font-medium text-rose-500">
                  Quality Health
                </span>
              </h2>

              {/* Score formula banner */}
              <div className="mb-6 flex items-center gap-3 px-5 py-3.5 rounded-2xl bg-[#0059B5]/5 dark:bg-[#60A5FA]/5 border border-[#0059B5]/10 dark:border-[#60A5FA]/10">
                <div className="shrink-0 w-7 h-7 rounded-full bg-[#0059B5]/10 dark:bg-[#60A5FA]/10 flex items-center justify-center border border-[#0059B5]/20 dark:border-[#60A5FA]/20">
                  <span className="text-[#0059B5] dark:text-[#60A5FA] font-serif font-bold italic text-sm">
                    f
                  </span>
                </div>
                <p className="text-sm text-[#0059B5] dark:text-[#60A5FA] font-mono">
                  <span className="font-semibold">Health Score</span> =
                  (Completeness × 0.5) + (Consistency × 0.5)
                </p>
                <span className="ml-auto text-xs text-neutral-400 font-light hidden sm:block">
                  Hover a score to see per-table breakdown
                </span>
              </div>

              <div className="grid gap-6">
                {sortedProfiles.map((profile: any) => (
                  <div
                    key={profile.table}
                    id={`quality-table-${profile.table}`}
                    className="scroll-mt-44"
                  >
                    <GlassCard className="p-8">
                      <div className="flex justify-between items-start mb-4">
                        <div>
                          <h3 className="text-2xl font-light text-neutral-900 dark:text-white mb-2">
                            {profile.table}
                          </h3>
                          <div className="flex gap-4 text-sm font-light text-neutral-500">
                            <span>
                              Completeness:{" "}
                              <span className="font-medium text-neutral-700 dark:text-neutral-300">
                                {profile.completeness_score}%
                              </span>
                            </span>
                            <span>
                              Consistency:{" "}
                              <span className="font-medium text-neutral-700 dark:text-neutral-300">
                                {profile.consistency_score}%
                              </span>
                            </span>
                          </div>
                          <div className="mt-1.5 text-xs font-mono text-neutral-400 dark:text-neutral-500">
                            ({profile.completeness_score}% × 0.5) + (
                            {profile.consistency_score}% × 0.5) ={" "}
                            <span
                              className={clsx(
                                "font-semibold",
                                (profile.quality_score || 0) > 80
                                  ? "text-emerald-500"
                                  : (profile.quality_score || 0) > 60
                                    ? "text-amber-500"
                                    : "text-rose-500",
                              )}
                            >
                              {Math.round(profile.quality_score || 0)}%
                            </span>
                          </div>
                        </div>
                        <div
                          className={clsx(
                            "text-5xl font-light tabular-nums shrink-0 ml-4",
                            (profile.quality_score || 0) > 80
                              ? "text-emerald-500"
                              : (profile.quality_score || 0) > 60
                                ? "text-amber-500"
                                : "text-rose-500",
                          )}
                        >
                          {Math.round(profile.quality_score || 0)}%
                        </div>
                      </div>

                      {profile.issues && profile.issues.length > 0 ? (
                        <div className="bg-rose-500/5 dark:bg-rose-500/10 border border-rose-500/20 rounded-[1.5rem] p-6">
                          <h4 className="text-rose-700 dark:text-rose-400 font-medium mb-3 flex items-center gap-2">
                            <ActivitySquare className="w-4 h-4" /> Detected
                            Issues
                          </h4>
                          <ul className="list-disc list-inside space-y-1 text-sm font-light text-rose-900/80 dark:text-rose-200/80 mb-6">
                            {profile.issues.map((issue: string, i: number) => (
                              <li key={i}>{issue}</li>
                            ))}
                          </ul>

                          {/* Data Trace Injection */}
                          <h5 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-3 border-t border-black/5 dark:border-white/5 pt-4">
                            Data Trace Inspections
                          </h5>
                          <div className="flex flex-col gap-5">
                            <div className="flex flex-col gap-2">
                              <span className="text-[10px] uppercase font-bold text-emerald-600 dark:text-emerald-400 tracking-wider">
                                Valid Sample Record
                              </span>
                              <div className="bg-emerald-500/5 dark:bg-emerald-500/10 border border-emerald-500/20 rounded-xl overflow-x-auto">
                                {renderRowTable(
                                  analysisData?.sample_tables?.[
                                    profile.table
                                  ]?.[0] || { status: "OK", mock_data: "true" },
                                  "emerald",
                                )}
                              </div>
                            </div>

                            <div className="flex flex-col gap-2">
                              <span className="text-[10px] uppercase font-bold text-rose-600 dark:text-rose-400 tracking-wider">
                                Violation Trace Snapshots
                              </span>
                              <div className="flex flex-col gap-2">
                                {((
                                  analysisData?.sample_tables?.[
                                    profile.table
                                  ] || []
                                ).length > 1
                                  ? (
                                      analysisData.sample_tables[
                                        profile.table
                                      ] as any[]
                                    ).slice(
                                      1,
                                      Math.min(4, profile.issues.length + 1),
                                    )
                                  : [
                                      {
                                        _error: "MOCKED VIOLATION",
                                        anomaly: "Missing parameter",
                                      },
                                    ]
                                ).map((row: any, i: number) => (
                                  <div
                                    key={i}
                                    className="bg-rose-500/5 dark:bg-rose-500/10 border border-rose-500/20 rounded-xl overflow-x-auto relative group"
                                  >
                                    {renderRowTable(row, "rose")}
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="text-emerald-600 dark:text-emerald-400 font-light flex items-center gap-2">
                          <ShieldCheck className="w-5 h-5" /> No issues detected
                        </div>
                      )}
                    </GlassCard>
                  </div>
                ))}
              </div>
            </div>
          );
        })()}
      </div>

      {/* SEMANTIC */}
      <div
        className={clsx(
          "animate-in fade-in duration-700 w-full mt-24 print:mt-10 print:break-after-page print:block",
          activeTab !== "semantic" && "hidden",
        )}
      >
        <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">
          Semantic{" "}
          <span className="font-medium text-[#0059B5]">Intelligence Layer</span>
        </h2>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-8">
          <GlassCard className="p-6">
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-2">
              Config Version
            </h3>
            <div className="text-3xl font-light text-neutral-900 dark:text-neutral-100">
              {String(semanticLayer?.config_version || "n/a")}
            </div>
          </GlassCard>
          <GlassCard className="p-6">
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-2">
              Avg Role Confidence
            </h3>
            <div className="text-3xl font-light text-[#0059B5] dark:text-[#60A5FA]">
              {Number(semanticLayer?.avg_role_confidence || 0).toFixed(2)}
            </div>
          </GlassCard>
          <GlassCard className="p-6">
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-2">
              Constraint Violations
            </h3>
            <div
              className={clsx(
                "text-3xl font-light",
                semanticConstraints.length > 0
                  ? "text-rose-500"
                  : "text-emerald-500",
              )}
            >
              {semanticConstraints.length}
            </div>
          </GlassCard>
          <GlassCard className="p-6">
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-2">
              Ambiguous Columns
            </h3>
            <div
              className={clsx(
                "text-3xl font-light",
                semanticAmbiguities.length > 0
                  ? "text-amber-500"
                  : "text-emerald-500",
              )}
            >
              {semanticAmbiguities.length}
            </div>
          </GlassCard>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <GlassCard className="overflow-hidden">
            <div className="px-6 py-4 border-b border-black/5 dark:border-white/5 bg-black/5 dark:bg-white/5">
              <h3 className="text-lg font-medium text-neutral-900 dark:text-neutral-100">
                Table Entity Mapping
              </h3>
            </div>
            <div className="p-4 max-h-[280px] overflow-auto">
              {semanticEntities.length === 0 ? (
                <p className="text-sm text-neutral-400">
                  No semantic entities detected.
                </p>
              ) : (
                <div className="space-y-2">
                  {semanticEntities.map((r: any, i: number) => (
                    <div
                      key={i}
                      className="flex items-center justify-between text-sm border-b border-black/5 dark:border-white/5 pb-2 last:border-0"
                    >
                      <span className="font-medium text-neutral-700 dark:text-neutral-200">
                        {String(r.table)}
                      </span>
                      <span className="text-neutral-500">
                        {String(r.entity)} (
                        {Number(r.confidence || 0).toFixed(2)})
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </GlassCard>

          <GlassCard className="overflow-hidden">
            <div className="px-6 py-4 border-b border-black/5 dark:border-white/5 bg-black/5 dark:bg-white/5">
              <h3 className="text-lg font-medium text-neutral-900 dark:text-neutral-100">
                Semantic Metrics
              </h3>
            </div>
            <div className="p-4 max-h-[280px] overflow-auto">
              {semanticMetrics.length === 0 ? (
                <p className="text-sm text-neutral-400">
                  No semantic metrics available.
                </p>
              ) : (
                <div className="space-y-3">
                  {semanticMetrics.map((m: any, i: number) => (
                    <div
                      key={i}
                      className="rounded-xl border border-black/5 dark:border-white/10 p-3 bg-white/40 dark:bg-black/20"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-neutral-800 dark:text-neutral-100">
                          {String(m.name)}
                        </span>
                        <span
                          className={clsx(
                            "text-xs px-2 py-0.5 rounded-full",
                            String(m.status) === "ok"
                              ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                              : "bg-amber-500/15 text-amber-700 dark:text-amber-400",
                          )}
                        >
                          {String(m.status || "ok")}
                        </span>
                      </div>
                      <div className="text-xs text-neutral-500 mt-1">
                        kind: {String(m.kind)} | value: {String(m.value)}
                      </div>
                      {m.note ? (
                        <div className="text-xs text-neutral-400 mt-1">
                          {String(m.note)}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </GlassCard>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <GlassCard className="overflow-hidden">
            <div className="px-6 py-4 border-b border-black/5 dark:border-white/5 bg-black/5 dark:bg-white/5">
              <h3 className="text-lg font-medium text-neutral-900 dark:text-neutral-100">
                Constraint Violations
              </h3>
            </div>
            <div className="p-4 max-h-[320px] overflow-auto">
              {semanticConstraints.length === 0 ? (
                <p className="text-sm text-emerald-600 dark:text-emerald-400">
                  No semantic constraint violations detected.
                </p>
              ) : (
                <div className="space-y-2">
                  {semanticConstraints.map((v: any, i: number) => (
                    <div
                      key={i}
                      className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-3"
                    >
                      <div className="text-xs text-rose-500 font-semibold uppercase tracking-wider">
                        {String(v.severity || "warning")}
                      </div>
                      <div className="text-sm text-rose-700 dark:text-rose-300 mt-1">
                        {String(v.message || "")}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </GlassCard>

          <GlassCard className="overflow-hidden">
            <div className="px-6 py-4 border-b border-black/5 dark:border-white/5 bg-black/5 dark:bg-white/5">
              <h3 className="text-lg font-medium text-neutral-900 dark:text-neutral-100">
                Top Mapping Suggestions
              </h3>
            </div>
            <div className="p-4 max-h-[320px] overflow-auto">
              {semanticSuggestions.length === 0 ? (
                <p className="text-sm text-neutral-400">
                  No semantic suggestions available.
                </p>
              ) : (
                <div className="space-y-2">
                  {semanticSuggestions.slice(0, 25).map((s: any, i: number) => (
                    <div
                      key={i}
                      className="rounded-xl border border-black/5 dark:border-white/10 p-3 bg-white/40 dark:bg-black/20"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-neutral-800 dark:text-neutral-100">
                          {String(s.table)}.{String(s.column)}
                        </span>
                        <span className="text-xs text-neutral-500">
                          {Number(s.confidence || 0).toFixed(2)}
                        </span>
                      </div>
                      <div className="text-xs text-neutral-500 mt-1">
                        role: {String(s.suggested_role)} | entity:{" "}
                        {String(s.entity)}
                      </div>
                      {s.explanation ? (
                        <div className="text-xs text-neutral-400 mt-1">
                          {String(s.explanation)}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </GlassCard>
        </div>
      </div>

      {/* ER GRAPH */}
      <div
        className={clsx(
          "animate-in fade-in duration-700 w-full mt-24 flex flex-col h-[calc(100vh-120px)] print:hidden",
          activeTab !== "er" && "hidden",
        )}
      >
        <div className="mb-6 shrink-0 flex items-center justify-between gap-3">
          <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white">
            Entity{" "}
            <span className="font-medium inline-block relative border-b border-rose-500/30">
              Relationships
            </span>
          </h2>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={copyMermaidCode}
              className="px-4 py-2 rounded-full text-sm font-medium border border-black/10 dark:border-white/10 bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 text-neutral-700 dark:text-neutral-200 transition-colors"
            >
              Copy Mermaid
            </button>
            <button
              onClick={downloadErAsSvg}
              className="px-4 py-2 rounded-full text-sm font-medium border border-black/10 dark:border-white/10 bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 text-neutral-700 dark:text-neutral-200 transition-colors"
            >
              Download SVG
            </button>
            <button
              onClick={downloadErAsPng}
              className="px-4 py-2 rounded-full text-sm font-medium border border-blue-200 dark:border-blue-800 bg-blue-500/10 hover:bg-blue-500/20 text-blue-700 dark:text-blue-300 transition-colors"
            >
              Download PNG
            </button>
          </div>
        </div>
        {copyStatus && (
          <div className="mb-3 text-xs text-neutral-500 dark:text-neutral-400">
            {copyStatus}
          </div>
        )}
        <div className="mb-4 text-xs text-neutral-500 dark:text-neutral-400">
          Processing limits: up to{" "}
          {processedRowLimit <= 0
            ? "all available"
            : processedRowLimit.toLocaleString()}{" "}
          profiled rows per table, with 50 sample rows per table in API payload.
        </div>
        <GlassCard className="p-0 flex-1 flex justify-center overflow-hidden w-full relative min-h-[600px]">
          <div ref={erDiagramRef} className="w-full h-full">
            <ERDiagram analysisData={analysisData} />
          </div>
        </GlassCard>
      </div>

      {/* DICTIONARY */}
      <div
        className={clsx(
          "w-full mt-24 print:mt-10 print:break-after-page print:block",
          activeTab !== "dictionary" && "hidden",
        )}
      >
        {(() => {
          const dictionary = analysisData?.data_dict || [];
          const dictTables = Array.from(
            new Set(dictionary.map((r: any) => r.table)),
          ) as string[];
          return (
            <div className="w-full">
              <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">
                Data{" "}
                <span className="font-medium text-[#0059B5]">Dictionary</span>
              </h2>

              <div className="mb-6 flex">
                <input
                  value={dictSearch}
                  onChange={(e) => setDictSearch(e.target.value)}
                  placeholder="Search table or column..."
                  className="w-full max-w-sm px-5 py-3 bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 rounded-2xl focus:outline-none focus:ring-2 focus:ring-[#0059B5] placeholder:text-neutral-400 font-light"
                />
              </div>
              <div className="space-y-6">
                {dictionary.length === 0 && (
                  <GlassCard className="p-8 text-center text-neutral-400">
                    Dictionary not generated.
                  </GlassCard>
                )}
                {dictTables.map((tableName) => {
                  const rows = dictionary.filter(
                    (r: any) =>
                      r.table === tableName &&
                      (String(r.column)
                        .toLowerCase()
                        .includes(dictSearch.toLowerCase()) ||
                        String(r.table)
                          .toLowerCase()
                          .includes(dictSearch.toLowerCase())),
                  );
                  if (rows.length === 0) return null;
                  return (
                    <GlassCard
                      key={String(tableName)}
                      id={`dict-table-${tableName}`}
                      className="overflow-hidden scroll-mt-44"
                    >
                      <div className="bg-black/5 dark:bg-white/5 backdrop-blur-md px-6 py-4 border-b border-black/5 dark:border-white/5 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-white dark:bg-black shadow-sm border border-black/5 dark:border-white/5">
                          <ListTree className="w-5 h-5 text-[#0059B5] dark:text-[#60A5FA]" />
                        </div>
                        <h3 className="font-medium text-lg text-neutral-900 dark:text-white">
                          {String(tableName)}
                        </h3>
                        <span className="ml-auto text-xs font-medium text-neutral-500 bg-black/5 dark:bg-white/10 px-3 py-1 rounded-full">
                          {rows.length} attributes
                        </span>
                      </div>
                      <div className="overflow-x-auto p-0 max-h-[400px]">
                        <table className="w-full text-left text-sm text-neutral-600 dark:text-neutral-300">
                          <thead className="sticky top-0 bg-white/80 dark:bg-black/80 backdrop-blur-xl z-10 border-b border-black/5 dark:border-white/5">
                            <tr>
                              <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400 w-1/4">
                                Column
                              </th>
                              <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400 w-1/6">
                                Data Type
                              </th>
                              <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400 w-1/4">
                                Role & Flags
                              </th>
                              <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400">
                                Description
                              </th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-black/5 dark:divide-white/5">
                            {rows.map((row: any, i: number) => (
                              <tr
                                key={i}
                                className="hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                              >
                                <td className="px-6 py-4 font-medium text-neutral-900 dark:text-neutral-100">
                                  {row.column}
                                </td>
                                <td className="px-6 py-4">
                                  <span className="font-mono text-xs text-[#0059B5] dark:text-[#60A5FA] bg-[#0059B5]/10 dark:bg-[#60A5FA]/10 px-2 py-1 rounded-md">
                                    {row.data_type}
                                  </span>
                                </td>
                                <td className="px-6 py-4 font-light">
                                  <div className="flex gap-2 items-center flex-wrap">
                                    <span
                                      className={clsx(
                                        "px-2 py-1.5 rounded-md text-xs font-medium",
                                        String(row.role).includes("primary_key")
                                          ? "bg-emerald-500/10 text-emerald-600 flex w-fit"
                                          : String(row.role).includes(
                                                "foreign_key",
                                              )
                                            ? "bg-amber-500/10 text-amber-600 flex w-fit"
                                            : "bg-neutral-500/10 text-neutral-500 flex w-fit",
                                      )}
                                    >
                                      {row.role || "dimension"}
                                    </span>
                                    {(String(row.column)
                                      .toLowerCase()
                                      .includes("email") ||
                                      String(row.column)
                                        .toLowerCase()
                                        .includes("phone") ||
                                      String(row.column)
                                        .toLowerCase()
                                        .includes("address") ||
                                      String(row.column)
                                        .toLowerCase()
                                        .includes("name")) && (
                                      <span className="px-2 py-1.5 rounded-md text-xs font-medium bg-purple-500/10 text-purple-600 dark:text-purple-400">
                                        PII
                                      </span>
                                    )}
                                    {(String(row.column)
                                      .toLowerCase()
                                      .includes("card") ||
                                      String(row.column)
                                        .toLowerCase()
                                        .includes("stripe") ||
                                      String(row.column)
                                        .toLowerCase()
                                        .includes("payment")) && (
                                      <span className="px-2 py-1.5 rounded-md text-xs font-medium bg-rose-500/10 text-rose-600 dark:text-rose-400">
                                        PCI-DSS
                                      </span>
                                    )}
                                  </div>
                                </td>
                                <td className="px-6 py-4 font-light max-w-xs">
                                  {row.description || "-"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </GlassCard>
                  );
                })}
              </div>
            </div>
          );
        })()}
      </div>

      {/* EXPORTS */}
      <div
        className={clsx(
          "animate-in fade-in duration-700 w-full mt-24 print:hidden",
          activeTab !== "exports" && "hidden",
        )}
      >
        {(() => {
          const downloadJSON = () => {
            const dataStr =
              "data:text/json;charset=utf-8," +
              encodeURIComponent(
                JSON.stringify(analysisData?.analysis, null, 2),
              );
            const anchor = document.createElement("a");
            anchor.href = dataStr;
            anchor.download = "nexus_analysis_export.json";
            anchor.click();
          };

          const downloadDbt = () => {
            const profiles = analysisData?.analysis?.table_profiles || [];
            let dbtYaml = "version: 2\n\nmodels:\n";
            profiles.forEach((p: any) => {
              dbtYaml += `  - name: ${p.table}\n    description: "Autogenerated by Nexus Intelligence"\n    columns:\n`;
              p.column_profiles?.forEach((col: any) => {
                dbtYaml += `      - name: ${col.column}\n        description: "${col.semantic_role || "No description"}"\n`;
              });
            });
            const dataStr =
              "data:text/yaml;charset=utf-8," + encodeURIComponent(dbtYaml);
            const anchor = document.createElement("a");
            anchor.href = dataStr;
            anchor.download = "nexus_dbt_schema.yml";
            anchor.click();
          };

          const downloadDictionaryCsv = () => {
            const rows = Array.isArray(analysisData?.data_dict)
              ? analysisData.data_dict
              : [];
            if (rows.length === 0) {
              alert("No data dictionary available to export.");
              return;
            }
            const headers: string[] = Array.from(
              new Set(
                rows.flatMap((row: Record<string, unknown>) =>
                  Object.keys(row).map(String),
                ),
              ),
            );
            const escapeCsv = (value: unknown) => {
              const text = String(value ?? "");
              if (/[",\n]/.test(text)) {
                return `"${text.replace(/"/g, '""')}"`;
              }
              return text;
            };
            const csv = [
              headers.join(","),
              ...rows.map((row: Record<string, unknown>) =>
                headers.map((header) => escapeCsv(row[header])).join(","),
              ),
            ].join("\n");

            const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = "nexus_data_dictionary.csv";
            anchor.click();
            URL.revokeObjectURL(url);
          };

          const downloadErSvgFromMermaid = async () => {
            const mermaidCode = String(analysisData?.er_diagram || "").trim();
            if (!mermaidCode) {
              alert("No ER diagram is available for export.");
              return;
            }
            try {
              mermaid.initialize({
                startOnLoad: false,
                theme: "base",
                securityLevel: "loose",
              });
              const renderId = `nexus-export-${Date.now()}`;
              const rendered = await mermaid.render(renderId, mermaidCode);
              const blob = new Blob([rendered.svg], {
                type: "image/svg+xml;charset=utf-8",
              });
              const url = URL.createObjectURL(blob);
              const anchor = document.createElement("a");
              anchor.href = url;
              anchor.download = "nexus_er_diagram.svg";
              anchor.click();
              URL.revokeObjectURL(url);
            } catch (error) {
              console.error("Failed to export ER SVG", error);
              alert(
                "Could not export ER SVG. Please open ER Diagram tab once and try again.",
              );
            }
          };

          return (
            <div className="animate-in fade-in duration-700 w-full mt-24">
              <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">
                Export{" "}
                <span className="font-medium text-[#0059B5]">Package</span>
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
                <GlassCard
                  className="p-8 flex items-start gap-6 hover:scale-[1.02] transition-transform cursor-pointer"
                  aria-label="JSON Export"
                >
                  <div className="w-14 h-14 rounded-2xl bg-[#0059B5]/10 dark:bg-[#60A5FA]/10 flex items-center justify-center shrink-0">
                    <Database className="w-6 h-6 text-[#0059B5] dark:text-[#60A5FA]" />
                  </div>
                  <div className="flex-1 text-left">
                    <h3 className="text-xl font-medium text-neutral-900 dark:text-white mb-2">
                      Analysis Payload (JSON)
                    </h3>
                    <p className="text-neutral-500 text-sm font-light mb-6">
                      Complete end-to-end extraction JSON payload representing
                      the entire relational model.
                    </p>
                    <button
                      onClick={downloadJSON}
                      className="bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 text-black dark:text-white px-6 py-2.5 rounded-full text-sm font-medium transition-colors border border-black/10 dark:border-white/10"
                    >
                      Download .json
                    </button>
                  </div>
                </GlassCard>

                <GlassCard
                  className="p-8 flex items-start gap-6 hover:scale-[1.02] transition-transform cursor-pointer"
                  aria-label="CSV Export"
                >
                  <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 flex items-center justify-center shrink-0">
                    <ListTree className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <div className="flex-1 text-left">
                    <h3 className="text-xl font-medium text-neutral-900 dark:text-white mb-2">
                      Data Dictionary (CSV)
                    </h3>
                    <p className="text-neutral-500 text-sm font-light mb-6">
                      Spreadsheet-ready schema attributes, AI definitions, and
                      semantic roles.
                    </p>
                    <button
                      onClick={downloadDictionaryCsv}
                      className="bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 px-6 py-2.5 rounded-full text-sm font-medium transition-colors border border-emerald-500/20"
                    >
                      Download .csv
                    </button>
                  </div>
                </GlassCard>

                <GlassCard
                  className="p-8 flex items-start gap-6 hover:scale-[1.02] transition-transform cursor-pointer"
                  aria-label="dbt Export"
                >
                  <div className="w-14 h-14 rounded-2xl bg-purple-500/10 flex items-center justify-center shrink-0">
                    <ActivitySquare className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div className="flex-1 text-left">
                    <h3 className="text-xl font-medium text-neutral-900 dark:text-white mb-2">
                      dbt Models (YAML)
                    </h3>
                    <p className="text-neutral-500 text-sm font-light mb-6">
                      Production-ready `schema.yml` configurations for your
                      analytics deployment.
                    </p>
                    <button
                      onClick={downloadDbt}
                      className="bg-purple-500/10 hover:bg-purple-500/20 text-purple-700 dark:text-purple-400 px-6 py-2.5 rounded-full text-sm font-medium transition-colors border border-purple-500/20"
                    >
                      Download .yml
                    </button>
                  </div>
                </GlassCard>

                <GlassCard
                  className="p-8 flex items-start gap-6 hover:scale-[1.02] transition-transform cursor-pointer"
                  aria-label="SVG ER Export"
                >
                  <div className="w-14 h-14 rounded-2xl bg-rose-500/10 flex items-center justify-center shrink-0">
                    <Share2 className="w-6 h-6 text-rose-600 dark:text-rose-400" />
                  </div>
                  <div className="flex-1 text-left">
                    <h3 className="text-xl font-medium text-neutral-900 dark:text-white mb-2">
                      Architectural ERD (SVG)
                    </h3>
                    <p className="text-neutral-500 text-sm font-light mb-6">
                      High-resolution vector graphic of the inferred entity
                      relationship layout.
                    </p>
                    <button
                      onClick={() => void downloadErSvgFromMermaid()}
                      className="bg-rose-500/10 hover:bg-rose-500/20 text-rose-700 dark:text-rose-400 px-6 py-2.5 rounded-full text-sm font-medium transition-colors border border-rose-500/20"
                    >
                      Download .svg
                    </button>
                  </div>
                </GlassCard>
              </div>
            </div>
          );
        })()}
      </div>

      {/* AI REVIEW */}
      <div
        className={clsx(
          "animate-in fade-in duration-700 w-full mt-24 print:mt-10 print:block",
          activeTab !== "ai" && "hidden",
        )}
      >
        <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">
          AI <span className="font-medium text-purple-500">Analyst Review</span>
        </h2>
        {analysisData?.ai_brief || aiResponse ? (
          <GlassCard className="p-10 relative overflow-hidden">
            {/* Print Header */}
            <div className="hidden print:block mb-8 pb-4 border-b border-black">
              <h1 className="text-2xl font-bold">
                Nexus Intelligence - Executive Summary
              </h1>
              <p className="text-sm font-mono mt-1 text-gray-500">
                Report Generated: {new Date().toLocaleDateString()}
              </p>
            </div>
            {isGeneratingAi && (
              <div className="absolute inset-0 bg-white/40 dark:bg-black/40 backdrop-blur-sm z-10 flex items-center justify-center print:hidden">
                <div className="flex flex-col items-center gap-4">
                  <Loader2 className="w-10 h-10 text-purple-500 animate-spin" />
                  <span className="text-purple-600 dark:text-purple-400 font-medium tracking-widest text-xs uppercase animate-pulse">
                    Running Neural Pipeline...
                  </span>
                </div>
              </div>
            )}
            <div className="mb-8 relative z-0 print:hidden">
              <textarea
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                className="w-full h-24 p-5 bg-white/50 dark:bg-black/20 border border-black/5 dark:border-white/10 rounded-2xl focus:outline-none focus:ring-1 focus:ring-purple-500 resize-none font-light text-sm shadow-inner dark:text-neutral-200"
                placeholder="Ask the AI agent..."
              />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                <select
                  value={aiProvider}
                  onChange={(e) =>
                    setAiProvider(
                      e.target.value === "ollama" ? "ollama" : "gemini",
                    )
                  }
                  className="w-full px-4 py-2.5 rounded-xl bg-white/50 dark:bg-black/20 border border-black/5 dark:border-white/10 text-sm"
                >
                  <option value="gemini">Gemini (API)</option>
                  <option value="ollama">Ollama (Local)</option>
                </select>

                {aiProvider === "gemini" ? (
                  <input
                    value={aiGeminiModel}
                    onChange={(e) => setAiGeminiModel(e.target.value)}
                    placeholder="Gemini model"
                    className="w-full px-4 py-2.5 rounded-xl bg-white/50 dark:bg-black/20 border border-black/5 dark:border-white/10 text-sm"
                  />
                ) : (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => refreshAiOllamaModels(aiOllamaEndpoint)}
                      className="px-3 py-2.5 rounded-xl bg-black/5 dark:bg-white/10 border border-black/10 dark:border-white/10 text-sm"
                    >
                      {aiModelLoading
                        ? "Refreshing..."
                        : "Refresh Ollama Models"}
                    </button>
                    <input
                      value={aiOllamaEndpoint}
                      onChange={(e) => setAiOllamaEndpoint(e.target.value)}
                      placeholder="Ollama endpoint"
                      className="flex-1 px-4 py-2.5 rounded-xl bg-white/50 dark:bg-black/20 border border-black/5 dark:border-white/10 text-sm"
                    />
                  </div>
                )}
              </div>
              {aiProvider === "gemini" ? (
                <input
                  value={aiGeminiApiKey}
                  onChange={(e) => setAiGeminiApiKey(e.target.value)}
                  type="password"
                  placeholder="Gemini API key (optional if configured in backend secrets)"
                  className="w-full mt-3 px-4 py-2.5 rounded-xl bg-white/50 dark:bg-black/20 border border-black/5 dark:border-white/10 text-sm"
                />
              ) : aiOllamaModels.length > 0 ? (
                <select
                  value={aiOllamaModel}
                  onChange={(e) => setAiOllamaModel(e.target.value)}
                  className="w-full mt-3 px-4 py-2.5 rounded-xl bg-white/50 dark:bg-black/20 border border-black/5 dark:border-white/10 text-sm"
                >
                  {aiOllamaModels.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  value={aiOllamaModel}
                  onChange={(e) => setAiOllamaModel(e.target.value)}
                  placeholder="Ollama model"
                  className="w-full mt-3 px-4 py-2.5 rounded-xl bg-white/50 dark:bg-black/20 border border-black/5 dark:border-white/10 text-sm"
                />
              )}
              <div className="flex justify-between mt-4">
                <button
                  onClick={() => window.print()}
                  className="px-6 py-2.5 bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300 rounded-full font-medium text-sm transition-colors border border-black/5 flex items-center gap-2 cursor-pointer hover:bg-neutral-200 dark:hover:bg-neutral-700"
                >
                  <Download className="w-4 h-4" /> Download PDF Report
                </button>
                <button
                  onClick={handleAiAction}
                  disabled={isGeneratingAi}
                  className="px-6 py-2.5 bg-purple-500/10 hover:bg-purple-500/20 text-purple-600 dark:text-purple-400 rounded-full font-medium text-sm transition-colors border border-purple-500/20 flex items-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  <BrainCircuit className="w-4 h-4" />{" "}
                  {isGeneratingAi ? "Generating..." : "Generate Analyst Brief"}
                </button>
              </div>
              {aiError && (
                <div className="mt-3 text-sm text-rose-600 dark:text-rose-400">
                  {aiError}
                </div>
              )}
              {aiOrchestration && (
                <div className="mt-3 text-xs text-neutral-500 dark:text-neutral-400">
                  Provider: {String(aiOrchestration.provider_used || "unknown")}{" "}
                  | Status: {String(aiOrchestration.status || "unknown")}
                </div>
              )}
            </div>
            <div className="prose prose-neutral dark:prose-invert max-w-none text-base font-light leading-relaxed whitespace-pre-wrap border-t border-black/5 dark:border-white/5 pt-8 relative z-0">
              <div
                dangerouslySetInnerHTML={{
                  __html: formatAiBriefToHtml(
                    aiResponse || analysisData.ai_brief || "",
                  ),
                }}
              />
            </div>
          </GlassCard>
        ) : (
          <GlassCard className="p-12 text-center text-neutral-400 font-light">
            AI module was skipped or unavailable for this run.
          </GlassCard>
        )}
      </div>

      {/* EDITOR */}
      <div
        className={clsx(
          "animate-in fade-in duration-700 w-full mt-24 print:hidden",
          activeTab !== "editor" && "hidden",
        )}
      >
        {(() => {
          const editRows =
            analysisData?.sample_tables?.[currentEditorTarget] || [];
          const editCols = editRows.length > 0 ? Object.keys(editRows[0]) : [];

          return (
            <div className="w-full">
              <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">
                Data{" "}
                <span className="font-medium text-amber-600 dark:text-amber-500">
                  Editor
                </span>
              </h2>
              <div className="mb-6 flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
                {tables.map((t: string) => (
                  <button
                    key={t}
                    onClick={() => setEditorTarget(t)}
                    className={clsx(
                      "px-4 py-2 rounded-xl text-sm transition-colors whitespace-nowrap",
                      currentEditorTarget === t
                        ? "bg-amber-500/10 text-amber-700 dark:text-amber-400 font-medium"
                        : "bg-black/5 dark:bg-white/5 text-neutral-500 hover:text-neutral-900 dark:hover:text-white font-light",
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>

              <GlassCard className="overflow-hidden p-0">
                <div className="bg-amber-500/10 text-amber-800 dark:text-amber-400 text-xs px-6 py-3 font-medium flex items-center gap-2">
                  <ActivitySquare className="w-4 h-4" /> Live Row Editor
                  (Changes sync to output payload)
                </div>
                <div className="overflow-x-auto overflow-y-auto max-h-[600px] bg-white/50 dark:bg-black/20">
                  <table className="w-full text-left text-sm border-collapse min-w-max">
                    <thead>
                      <tr>
                        {editCols.map((c: string) => (
                          <th
                            key={c}
                            className="px-4 py-3 font-medium uppercase tracking-wider text-[10px] text-neutral-400 border-b border-black/10 dark:border-white/10 bg-black/5 dark:bg-white/5 sticky top-0 z-10 whitespace-nowrap"
                          >
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-black/5 dark:divide-white/5">
                      {editRows.map((row: any, i: number) => (
                        <tr
                          key={i}
                          className="hover:bg-amber-500/5 transition-colors group"
                        >
                          {editCols.map((c: string) => (
                            <td
                              key={c}
                              className="px-4 py-2 font-light text-neutral-700 dark:text-neutral-300 outline-none focus:bg-amber-500/10 focus:ring-1 focus:ring-amber-500/50 transition-colors whitespace-nowrap max-w-[200px] truncate"
                              contentEditable
                              suppressContentEditableWarning
                            >
                              {String(row[c] || "")}
                            </td>
                          ))}
                        </tr>
                      ))}
                      {editRows.length === 0 && (
                        <tr>
                          <td
                            colSpan={editCols.length || 1}
                            className="px-6 py-8 text-center text-neutral-400 font-light"
                          >
                            No rows found in analyzed sample.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </GlassCard>
            </div>
          );
        })()}
      </div>

      {histTooltip && (
        <div
          className="fixed pointer-events-none z-[9999] px-3 py-2 bg-black dark:bg-white text-white dark:text-black rounded-lg shadow-2xl text-[11px] font-mono flex flex-col items-center gap-1 border border-white/20 dark:border-black/20"
          style={{
            left: histTooltip.x,
            top: histTooltip.y,
            transform: "translate(-50%, -100%)",
          }}
        >
          <span className="opacity-70">
            Bound: [{histTooltip.min} - {histTooltip.max}]
          </span>
          <span className="font-bold">Count: {histTooltip.count}</span>
          <div className="absolute top-[calc(100%-4px)] left-1/2 -translate-x-1/2 w-2 h-2 bg-black dark:bg-white rotate-45 rounded-sm" />
        </div>
      )}
    </div>
  );
}

// ------------------------------------
// MAIN APP
// ------------------------------------
export default function App() {
  const [appView, setAppView] = useState<"home" | "agent-settings">("home");
  const [ingestionState, setIngestionState] = useState<
    "idle" | "processing" | "db_form" | "done"
  >("idle");
  const [activeTab, setActiveTab] = useState("overview");
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [agentModalOpen, setAgentModalOpen] = useState(false);
  const [agentAuthState, setAgentAuthState] = useState<AgentAuthState>({
    ok: false,
    email: "",
    idToken: "",
  });
  const [agentWorking, setAgentWorking] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [agentInfo, setAgentInfo] = useState<string | null>(null);
  const [agentToast, setAgentToast] = useState<string | null>(null);
  const [agentLive, setAgentLive] = useState(false);
  const [agentAutoReplyEnabled, setAgentAutoReplyEnabled] = useState(false);
  const [agentLogs, setAgentLogs] = useState<Array<Record<string, unknown>>>(
    [],
  );
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    setReduceMotion(document.documentElement.classList.contains("reduced-motion"));
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((m) => {
        if (m.attributeName === "class") {
          setReduceMotion(document.documentElement.classList.contains("reduced-motion"));
        }
      });
    });
    observer.observe(document.documentElement, { attributes: true });
    return () => observer.disconnect();
  }, []);
  const [agentStatusRefreshing, setAgentStatusRefreshing] = useState(false);
  const [agentStatusUpdatedAt, setAgentStatusUpdatedAt] = useState<
    number | null
  >(null);
  const [secretVisibility, setSecretVisibility] = useState<
    Record<SecretFieldKey, boolean>
  >({
    firebaseLoginPassword: false,
    gmailAppPassword: false,
    geminiApiKey: false,
    dbPassword: false,
  });
  const [agentForm, setAgentForm] = useState<AgentFormState>({
    firebaseApiKey: "",
    firebaseAuthDomain: "",
    firebaseProjectId: "",
    firebaseStorageBucket: "",
    firebaseLoginEmail: "burplefolk@gmail.com",
    firebaseLoginPassword: "",
    agentEmail: "burplefolk@gmail.com",
    gmailAppPassword: "",
    imapHost: "imap.gmail.com",
    smtpHost: "smtp.gmail.com",
    smtpPort: 587,
    pollSeconds: 5,
    maxMessagesPerCycle: 5,
    aiProvider: "ollama",
    ollamaEndpoint: "http://localhost:11434",
    ollamaModel: "llama2",
    geminiApiKey: "",
    geminiModel: "gemini-2.0-flash",
  });

  const [dragActive, setDragActive] = useState(false);
  const [analysisRowLimit, setAnalysisRowLimit] = useState<number>(1000000);
  const [lastRunRowLimit, setLastRunRowLimit] = useState<number>(1000000);
  const hasAnalysis = ingestionState === "done" && Boolean(analysisData);

  const toggleSecretVisibility = (key: SecretFieldKey) => {
    setSecretVisibility((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const refreshAgentLogs = async () => {
    try {
      const res = await axios.get(`${API_BASE}/agent/logs`, {
        params: { limit: 100 },
      });
      setAgentLogs(Array.isArray(res.data?.events) ? res.data.events : []);
    } catch {
      // Keep UI responsive even if logs endpoint fails.
    }
  };

  const refreshAgentRuntimeStatus = async () => {
    setAgentStatusRefreshing(true);
    try {
      const res = await axios.get(`${API_BASE}/agent/auto-reply/status`);
      setAgentLive(Boolean(res.data?.live));
      setAgentAutoReplyEnabled(Boolean(res.data?.running));
      setAgentStatusUpdatedAt(Date.now());
    } catch {
      setAgentLive(false);
    } finally {
      setAgentStatusRefreshing(false);
    }
  };

  const loadOllamaModels = async (endpoint: string) => {
    try {
      const res = await axios.get(`${API_BASE}/agent/ollama-models`, {
        params: { endpoint },
      });
      const models = Array.isArray(res.data?.models)
        ? (res.data.models as string[])
        : [];
      setOllamaModels(models);
      if (models.length > 0) {
        setAgentForm((prev) => ({
          ...prev,
          ollamaModel: prev.ollamaModel || models[0],
        }));
      }
    } catch {
      setOllamaModels([]);
    }
  };

  useEffect(() => {
    const loadAgentDefaults = async () => {
      try {
        const res = await axios.get(`${API_BASE}/agent/defaults`);
        const defaults = res.data || {};
        const firebase = defaults.firebase || {};
        const models = Array.isArray(defaults.ollamaModels)
          ? (defaults.ollamaModels as string[])
          : [];
        setOllamaModels(models);
        setAgentForm((prev) => ({
          ...prev,
          firebaseApiKey: String(firebase.apiKey || prev.firebaseApiKey),
          firebaseAuthDomain: String(
            firebase.authDomain || prev.firebaseAuthDomain,
          ),
          firebaseProjectId: String(
            firebase.projectId || prev.firebaseProjectId,
          ),
          firebaseStorageBucket: String(
            firebase.storageBucket || prev.firebaseStorageBucket,
          ),
          firebaseLoginEmail: String(
            defaults.defaultAgentEmail || prev.firebaseLoginEmail,
          ),
          agentEmail: String(defaults.defaultAgentEmail || prev.agentEmail),
          imapHost: String(defaults.imapHost || prev.imapHost),
          smtpHost: String(defaults.smtpHost || prev.smtpHost),
          smtpPort: Number(defaults.smtpPort || prev.smtpPort),
          pollSeconds: Math.max(
            5,
            Math.min(60, Number(defaults.pollSeconds || prev.pollSeconds)),
          ),
          maxMessagesPerCycle: clamp(
            Number(defaults.maxMessagesPerCycle || prev.maxMessagesPerCycle),
            0,
            5,
          ),
          aiProvider: defaults.aiProvider === "gemini" ? "gemini" : "ollama",
          ollamaEndpoint: String(
            defaults.ollamaEndpoint || prev.ollamaEndpoint,
          ),
          ollamaModel: String(defaults.ollamaModel || prev.ollamaModel),
          geminiModel: String(defaults.geminiModel || prev.geminiModel),
        }));
      } catch {
        // Keep local defaults when backend defaults are unavailable.
      }
      refreshAgentLogs();
      refreshAgentRuntimeStatus();
    };
    loadAgentDefaults();
  }, []);

  const handleAgentLogin = async () => {
    setAgentWorking(true);
    setAgentError(null);
    setAgentInfo(null);
    try {
      const payload = {
        firebase_api_key: agentForm.firebaseApiKey,
        firebase_auth_domain: agentForm.firebaseAuthDomain,
        firebase_project_id: agentForm.firebaseProjectId,
        firebase_storage_bucket: agentForm.firebaseStorageBucket,
        email: agentForm.firebaseLoginEmail,
        password: agentForm.firebaseLoginPassword,
      };
      const res = await axios.post(`${API_BASE}/agent/login`, payload);
      if (res.data?.ok) {
        setAgentAuthState({
          ok: true,
          email: String(res.data.email || agentForm.firebaseLoginEmail),
          idToken: String(res.data.idToken || ""),
        });
        setAgentForm((prev) => ({
          ...prev,
          agentEmail: prev.agentEmail || prev.firebaseLoginEmail,
        }));
        setAgentToast("Authenticated successfully.");
        setAgentModalOpen(false);
        setAppView("home");
        await refreshAgentLogs();
        await refreshAgentRuntimeStatus();
      } else {
        setAgentError(
          String(res.data?.message || "Agent authentication failed."),
        );
      }
    } catch (err: any) {
      setAgentError(
        String(
          err?.response?.data?.detail ||
            err?.message ||
            "Agent authentication failed.",
        ),
      );
    } finally {
      setAgentWorking(false);
    }
  };

  useEffect(() => {
    if (!agentToast) {
      return;
    }
    const timer = window.setTimeout(() => setAgentToast(null), 3500);
    return () => window.clearTimeout(timer);
  }, [agentToast]);

  const applyAutoReplyState = async (enabled: boolean) => {
    if (!agentAuthState.ok) {
      setAgentError("Authenticate agent first.");
      setAgentAutoReplyEnabled(false);
      return;
    }
    if (enabled && !hasAnalysis) {
      setAgentError(
        "Analyze a dataset first before enabling automatic reply-all.",
      );
      setAgentAutoReplyEnabled(false);
      return;
    }
    if (enabled && (!agentForm.agentEmail || !agentForm.gmailAppPassword)) {
      setAgentError(
        "Enter Agent Gmail and Gmail App Password before enabling automatic reply-all.",
      );
      setAgentAutoReplyEnabled(false);
      return;
    }

    setAgentWorking(true);
    setAgentError(null);
    try {
      await axios.post(`${API_BASE}/agent/auto-reply`, {
        enable_auto_reply: enabled,
        poll_seconds: Math.max(5, Math.min(60, Number(agentForm.pollSeconds))),
        agent_email: agentForm.agentEmail,
        gmail_app_password: agentForm.gmailAppPassword,
        imap_host: agentForm.imapHost,
        smtp_host: agentForm.smtpHost,
        smtp_port: agentForm.smtpPort,
        max_messages_per_cycle: clamp(
          Number(agentForm.maxMessagesPerCycle),
          0,
          5,
        ),
        ai_provider: agentForm.aiProvider,
        ollama_endpoint: agentForm.ollamaEndpoint,
        ollama_model: agentForm.ollamaModel,
        gemini_api_key: agentForm.geminiApiKey,
        gemini_model: agentForm.geminiModel,
      });
      setAgentAutoReplyEnabled(enabled);
      setAgentInfo(
        enabled
          ? "Automatic reply-all enabled."
          : "Automatic reply-all disabled.",
      );
      await refreshAgentRuntimeStatus();
      await refreshAgentLogs();
    } catch (err: any) {
      setAgentError(
        String(
          err?.response?.data?.detail ||
            err?.message ||
            "Unable to update automatic reply-all state.",
        ),
      );
      await refreshAgentRuntimeStatus();
    } finally {
      setAgentWorking(false);
    }
  };

  useEffect(() => {
    if (appView !== "agent-settings" || !agentAuthState.ok) {
      return;
    }
    const timer = window.setInterval(() => {
      refreshAgentRuntimeStatus();
      refreshAgentLogs();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [appView, agentAuthState.ok]);

  const handleProcessInboxOnce = async () => {
    if (!hasAnalysis) {
      setAgentError(
        "Analyze a dataset first before processing inbox messages.",
      );
      return;
    }
    setAgentWorking(true);
    setAgentError(null);
    setAgentInfo(null);
    try {
      const payload = {
        agent_email: agentForm.agentEmail,
        gmail_app_password: agentForm.gmailAppPassword,
        imap_host: agentForm.imapHost,
        smtp_host: agentForm.smtpHost,
        smtp_port: agentForm.smtpPort,
        max_messages_per_cycle: clamp(
          Number(agentForm.maxMessagesPerCycle),
          0,
          5,
        ),
        ai_provider: agentForm.aiProvider,
        ollama_endpoint: agentForm.ollamaEndpoint,
        ollama_model: agentForm.ollamaModel,
        gemini_api_key: agentForm.geminiApiKey,
        gemini_model: agentForm.geminiModel,
      };
      const res = await axios.post(`${API_BASE}/agent/process-once`, payload);
      const summary = res.data?.summary || {};
      const replied = Number(summary.replied || 0);
      setAgentInfo(
        replied > 0
          ? `Agent sent ${replied} reply-all email(s).`
          : `No replies sent. Unseen: ${Number(summary.unseen_count || 0)}, Processed: ${Number(summary.processed || 0)}, Skipped: ${Number(summary.skipped || 0)}.`,
      );
      await refreshAgentLogs();
    } catch (err: any) {
      setAgentError(
        String(
          err?.response?.data?.detail ||
            err?.message ||
            "Inbox processing failed.",
        ),
      );
    } finally {
      setAgentWorking(false);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      setIngestionState("processing");
      const formData = new FormData();
      Array.from(files).forEach((file) => formData.append("files", file));
      formData.append("profile_row_limit", String(analysisRowLimit));
      try {
        const res = await axios.post(`${API_BASE}/analyze/csv`, formData);
        setAnalysisData(res.data);
        setLastRunRowLimit(analysisRowLimit);
        setIngestionState("done");
      } catch (err) {
        console.error(err);
        alert("Failed to analyze CSV.");
        setIngestionState("idle");
      }
    }
  };

  const [dbForm, setDbForm] = useState({
    db_type: "sqlite",
    host: "localhost",
    port: "1433",
    database: "",
    username: "",
    password: "",
  });

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setIngestionState("processing");
    const formData = new FormData();
    Array.from(files).forEach((file) => formData.append("files", file));
    formData.append("profile_row_limit", String(analysisRowLimit));

    try {
      const res = await axios.post(`${API_BASE}/analyze/csv`, formData);
      setAnalysisData(res.data);
      setLastRunRowLimit(analysisRowLimit);
      setIngestionState("done");
    } catch (e) {
      console.error(e);
      const message = axios.isAxiosError(e)
        ? (e.response?.data?.detail || e.message || "Unknown API error")
        : "Unknown API error";
      alert(
        `Failed to analyze. Ensure backend API is running. Backend target: ${API_BASE}\nError: ${message}`,
      );
      setIngestionState("idle");
    }
  };

  const handleDbSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIngestionState("processing");

    const formData = new FormData();
    Object.entries(dbForm).forEach(([key, val]) => formData.append(key, val));
    formData.append("profile_row_limit", String(analysisRowLimit));

    try {
      const res = await axios.post(`${API_BASE}/analyze/db`, formData);
      setAnalysisData(res.data);
      setLastRunRowLimit(analysisRowLimit);
      setIngestionState("done");
    } catch (e) {
      console.error(e);
      alert(
        "Database connection failed. Check your credentials and backend server!",
      );
      setIngestionState("idle");
    }
  };

  return (
    <MotionConfig reducedMotion={reduceMotion ? "always" : "user"}>
      <div className="min-h-screen bg-[#F5F5F7] dark:bg-[#0c0d0f] text-neutral-900 dark:text-neutral-100 font-sans transition-colors duration-500 relative">
        {/* Soulful Ambient Glows Background */}
        <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
          <div className="absolute top-[-20%] left-[-10%] w-[60vw] h-[60vw] rounded-full bg-blue-300/10 dark:bg-blue-600/10 blur-[140px]" />
          <div className="absolute top-[40%] right-[-10%] w-[50vw] h-[50vw] rounded-full bg-indigo-300/10 dark:bg-indigo-600/10 blur-[140px]" />
        </div>

      <div className="fixed top-6 right-6 z-[60] print-hidden">
        <SettingsMenu />
      </div>

      {/* Top Left Global Back Arrow */}
      {((ingestionState === "done" && appView === "home") ||
        appView === "agent-settings") && (
        <button
          onClick={() => {
            if (appView === "agent-settings") {
              setAppView("home");
            } else if (ingestionState === "done") {
              setIngestionState("idle");
              setAnalysisData(null);
              setActiveTab("overview");
            }
          }}
          className="fixed top-6 left-6 z-[60] h-10 w-10 flex items-center justify-center rounded-full bg-white/40 dark:bg-black/40 backdrop-blur-xl border border-black/5 dark:border-white/10 text-neutral-600 dark:text-neutral-400 hover:bg-white/70 dark:hover:bg-white/20 hover:text-neutral-900 dark:hover:text-white transition-all shadow-sm print-hidden"
          title={
            appView === "agent-settings"
              ? "Back to Dashboard"
              : "Start Over"
          }
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
      )}

      <TopNav
        activeTab={hasAnalysis && appView === "home" ? activeTab : undefined}
        setActiveTab={setActiveTab}
        showAnalysisNav={hasAnalysis && appView === "home"}
      >
        <div className="flex flex-row items-center gap-2">
          <button
            onClick={() => {
              setAgentError(null);
              setAgentInfo(null);
              if (agentAuthState.ok) {
                setAppView((prev) =>
                  prev === "agent-settings" ? "home" : "agent-settings",
                );
                return;
              }
              setAgentModalOpen(true);
            }}
            className={`h-[36px] px-4 rounded-full text-[13px] font-medium tracking-wide transition-all border print-hidden flex items-center justify-center gap-2 ${
              agentAuthState.ok
                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-500/20"
                : "bg-[#0059B5] border-transparent text-white hover:bg-[#004a99] dark:bg-[#60A5FA] dark:text-[#0b1220] dark:hover:bg-[#3b82f6]"
            }`}
          >
            <Mail className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Agent</span>
          </button>
        </div>
      </TopNav>

      {agentToast && (
        <div className="fixed top-24 left-1/2 -translate-x-1/2 z-[75] px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-700 dark:text-emerald-300 text-sm font-medium">
          {agentToast}
        </div>
      )}

      <main className="relative z-10 pt-20 pb-20 px-6 max-w-6xl mx-auto w-full min-h-[90vh] flex flex-col items-center">
        {appView === "agent-settings" && agentAuthState.ok ? (
          <div className="w-full mt-12">
            <div className="mb-8 flex flex-wrap items-center justify-between gap-3 border-b border-black/10 dark:border-white/10 pb-4">
              <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white">
                Agent{" "}
                <span className="font-medium text-emerald-500">Settings</span>
              </h2>
              <div className="flex items-center gap-2 rounded-xl border border-black/10 dark:border-white/10 bg-white/70 dark:bg-black/20 backdrop-blur-md px-3 py-2 shadow-sm">
                <span
                  className={clsx(
                    "px-2.5 py-1 text-xs font-semibold rounded-lg border inline-flex items-center gap-2",
                    agentLive
                      ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-700 dark:text-emerald-300"
                      : "bg-neutral-500/10 border-neutral-400/30 text-neutral-600 dark:text-neutral-300"
                  )}
                >
                  <span
                    className={clsx(
                      "inline-block w-2 h-2 rounded-full",
                      agentLive ? "bg-emerald-500 animate-pulse" : "bg-neutral-400"
                    )}
                  />
                  Agent {agentLive ? "Live" : "Idle"}
                  {agentStatusUpdatedAt
                    ? ` · ${new Date(agentStatusUpdatedAt).toLocaleTimeString()}`
                    : ""}
                </span>
                <button
                  onClick={refreshAgentRuntimeStatus}
                  className="p-1.5 rounded-md border border-black/10 dark:border-white/10 bg-white/70 dark:bg-black/30 hover:bg-white dark:hover:bg-black/50 transition-colors"
                  title="Refresh status"
                  aria-label="Refresh status"
                >
                  <RefreshCw
                    className={clsx(
                      "w-3.5 h-3.5",
                      agentStatusRefreshing && "animate-spin"
                    )}
                  />
                </button>
              </div>
            </div>

            {agentError && (
              <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
                {agentError}
              </div>
            )}
            {agentInfo && (
              <div className="mb-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-300 text-sm">
                {agentInfo}
              </div>
            )}

            <div className="bg-white/45 dark:bg-black/20 border border-white/40 dark:border-white/10 rounded-xl p-6 mb-6">
              <p className="text-sm text-neutral-600 dark:text-neutral-300">
                Logged in as:{" "}
                <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                  {agentAuthState.email}
                </span>
              </p>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <section className="bg-white/45 dark:bg-black/20 border border-white/40 dark:border-white/10 rounded-xl p-6 space-y-4">
                <h3 className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">
                  Gmail Configuration
                </h3>
                <div className="space-y-3">
                  <input
                    value={agentForm.agentEmail}
                    onChange={(e) =>
                      setAgentForm((prev) => ({
                        ...prev,
                        agentEmail: e.target.value,
                      }))
                    }
                    placeholder="Agent Gmail"
                    className="w-full px-4 py-3 rounded-lg bg-white/65 dark:bg-black/30 border border-black/10 dark:border-white/10"
                  />
                  <PasswordField
                    value={agentForm.gmailAppPassword}
                    onChange={(next) =>
                      setAgentForm((prev) => ({
                        ...prev,
                        gmailAppPassword: next,
                      }))
                    }
                    placeholder="Gmail App Password"
                    visible={secretVisibility.gmailAppPassword}
                    onToggle={() => toggleSecretVisibility("gmailAppPassword")}
                    className="w-full px-4 py-3 rounded-lg bg-white/65 dark:bg-black/30 border border-black/10 dark:border-white/10"
                  />
                  <input
                    value={agentForm.imapHost}
                    onChange={(e) =>
                      setAgentForm((prev) => ({
                        ...prev,
                        imapHost: e.target.value,
                      }))
                    }
                    placeholder="IMAP Host"
                    className="w-full px-4 py-3 rounded-lg bg-white/65 dark:bg-black/30 border border-black/10 dark:border-white/10"
                  />
                  <input
                    value={agentForm.smtpHost}
                    onChange={(e) =>
                      setAgentForm((prev) => ({
                        ...prev,
                        smtpHost: e.target.value,
                      }))
                    }
                    placeholder="SMTP Host"
                    className="w-full px-4 py-3 rounded-lg bg-white/65 dark:bg-black/30 border border-black/10 dark:border-white/10"
                  />
                  <input
                    type="number"
                    min={1}
                    value={agentForm.smtpPort}
                    onChange={(e) =>
                      setAgentForm((prev) => ({
                        ...prev,
                        smtpPort: Number(e.target.value || 587),
                      }))
                    }
                    placeholder="SMTP Port"
                    className="w-full px-4 py-3 rounded-lg bg-white/65 dark:bg-black/30 border border-black/10 dark:border-white/10"
                  />
                </div>
              </section>

              <section className="bg-white/45 dark:bg-black/20 border border-white/40 dark:border-white/10 rounded-xl p-6 space-y-4">
                <h3 className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">
                  AI Query Engine
                </h3>
                <div className="space-y-3">
                  <select
                    value={agentForm.aiProvider}
                    onChange={(e) =>
                      setAgentForm((prev) => ({
                        ...prev,
                        aiProvider:
                          e.target.value === "gemini" ? "gemini" : "ollama",
                      }))
                    }
                    className="w-full px-4 py-3 rounded-lg bg-white/65 dark:bg-black/30 border border-black/10 dark:border-white/10"
                  >
                    <option value="ollama">Ollama (local)</option>
                    <option value="gemini">Gemini (API key)</option>
                  </select>
                  {agentForm.aiProvider === "ollama" ? (
                    <>
                      <input
                        value={agentForm.ollamaEndpoint}
                        onChange={(e) =>
                          setAgentForm((prev) => ({
                            ...prev,
                            ollamaEndpoint: e.target.value,
                          }))
                        }
                        placeholder="Ollama Endpoint"
                        className="w-full px-4 py-3 rounded-lg bg-white/65 dark:bg-black/30 border border-black/10 dark:border-white/10"
                      />
                      {ollamaModels.length > 0 ? (
                        <select
                          value={agentForm.ollamaModel}
                          onChange={(e) =>
                            setAgentForm((prev) => ({
                              ...prev,
                              ollamaModel: e.target.value,
                            }))
                          }
                          className="w-full px-4 py-3 rounded-lg bg-white/65 dark:bg-black/30 border border-black/10 dark:border-white/10"
                        >
                          {ollamaModels.map((model) => (
                            <option key={model} value={model}>
                              {model}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          value={agentForm.ollamaModel}
                          onChange={(e) =>
                            setAgentForm((prev) => ({
                              ...prev,
                              ollamaModel: e.target.value,
                            }))
                          }
                          placeholder="Model"
                          className="w-full px-4 py-3 rounded-lg bg-white/65 dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                      )}
                      <button
                        onClick={() =>
                          loadOllamaModels(agentForm.ollamaEndpoint)
                        }
                        className="px-4 py-2.5 rounded-lg bg-black/5 dark:bg-white/10 border border-black/10 dark:border-white/10 text-sm font-medium"
                      >
                        Refresh Ollama Models
                      </button>
                    </>
                  ) : (
                    <>
                      <PasswordField
                        value={agentForm.geminiApiKey}
                        onChange={(next) =>
                          setAgentForm((prev) => ({
                            ...prev,
                            geminiApiKey: next,
                          }))
                        }
                        placeholder="Gemini API Key"
                        visible={secretVisibility.geminiApiKey}
                        onToggle={() => toggleSecretVisibility("geminiApiKey")}
                        className="w-full px-4 py-3 rounded-lg bg-white/65 dark:bg-black/30 border border-black/10 dark:border-white/10"
                      />
                      <input
                        value={agentForm.geminiModel}
                        onChange={(e) =>
                          setAgentForm((prev) => ({
                            ...prev,
                            geminiModel: e.target.value,
                          }))
                        }
                        placeholder="Gemini Model"
                        className="w-full px-4 py-3 rounded-lg bg-white/65 dark:bg-black/30 border border-black/10 dark:border-white/10"
                      />
                    </>
                  )}
                </div>
              </section>
            </div>

            <section className="bg-white/45 dark:bg-black/20 border border-white/40 dark:border-white/10 rounded-xl p-6 mt-6 space-y-4">
              <h3 className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">
                Automation
              </h3>
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Inbox poll interval (seconds)
                  </label>
                  <input
                    type="range"
                    min={5}
                    max={60}
                    step={5}
                    value={agentForm.pollSeconds}
                    onChange={(e) =>
                      setAgentForm((prev) => ({
                        ...prev,
                        pollSeconds: Number(e.target.value),
                      }))
                    }
                    className="w-full"
                  />
                  <div className="text-sm text-neutral-500 mt-1">
                    {agentForm.pollSeconds} seconds
                  </div>
                  <div className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                    Hard deadline enforced: every email should be
                    checked/replied within 60 seconds.
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Max emails per cycle
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={5}
                    step={1}
                    value={agentForm.maxMessagesPerCycle}
                    onChange={(e) =>
                      setAgentForm((prev) => ({
                        ...prev,
                        maxMessagesPerCycle: clamp(
                          Number(e.target.value),
                          0,
                          5,
                        ),
                      }))
                    }
                    className="w-full"
                  />
                  <div className="text-sm text-neutral-500 mt-1">
                    {agentForm.maxMessagesPerCycle}
                  </div>
                </div>
              </div>
              <label className="inline-flex items-center gap-2 text-sm font-medium">
                <input
                  type="checkbox"
                  checked={agentAutoReplyEnabled}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    setAgentAutoReplyEnabled(checked);
                    applyAutoReplyState(checked);
                  }}
                />
                Enable automatic reply-all
              </label>
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={handleProcessInboxOnce}
                  disabled={agentWorking || !hasAnalysis}
                  className="px-5 py-3 rounded-lg bg-[#0059B5] hover:bg-[#004289] text-white font-semibold disabled:opacity-60"
                >
                  {agentWorking ? "Processing..." : "Process inbox once now"}
                </button>
                <button
                  onClick={() => applyAutoReplyState(agentAutoReplyEnabled)}
                  disabled={agentWorking}
                  className="px-5 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold disabled:opacity-60"
                >
                  Apply Agent Settings
                </button>
              </div>
            </section>

            <section className="bg-white/45 dark:bg-black/20 border border-white/40 dark:border-white/10 rounded-xl p-6 mt-6 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">
                  Activity Logs
                </h3>
                <button
                  onClick={() => {
                    refreshAgentLogs();
                    refreshAgentRuntimeStatus();
                  }}
                  className="px-3 py-2 text-xs rounded-lg bg-black/5 dark:bg-white/10"
                >
                  Refresh
                </button>
              </div>
              <div className="max-h-72 overflow-y-auto rounded-lg border border-black/10 dark:border-white/10 bg-black/[0.03] dark:bg-white/[0.03] p-3">
                {agentLogs.length === 0 ? (
                  <p className="text-sm text-neutral-500">No logs yet.</p>
                ) : (
                  <div className="space-y-2">
                    {agentLogs.map((event, idx) => {
                      const ts = String(event.timestamp || "");
                      const level = String(event.level || "INFO").toUpperCase();
                      const msg = String(event.message || "");
                      const metadata = formatAgentLogMetadata(event.metadata);
                      const levelTone =
                        level === "ERROR"
                          ? "text-rose-600 dark:text-rose-300"
                          : level === "WARNING"
                            ? "text-amber-600 dark:text-amber-300"
                            : level === "DEBUG"
                              ? "text-sky-600 dark:text-sky-300"
                              : "text-emerald-600 dark:text-emerald-300";
                      return (
                        <div
                          key={`${ts}-${idx}`}
                          className="rounded-lg border border-black/10 dark:border-white/10 bg-white/70 dark:bg-black/25 px-3 py-2 text-xs break-words"
                        >
                          <div className="flex items-center gap-2 mb-1 text-[11px]">
                            <span className="text-neutral-500 dark:text-neutral-400">
                              {new Date(ts || Date.now()).toLocaleString()}
                            </span>
                            <span className={clsx("font-semibold", levelTone)}>
                              {level}
                            </span>
                          </div>
                          <div className="text-neutral-800 dark:text-neutral-100">
                            {msg}
                          </div>
                          {metadata ? (
                            <div className="text-neutral-500 dark:text-neutral-400 mt-1">
                              {metadata}
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </section>
          </div>
        ) : ingestionState === "done" ? (
          <div className="w-full relative min-h-full">
            <ErrorBoundary>
              <DataView
                activeTab={activeTab === "editor" ? "editor" : activeTab}
                analysisData={analysisData}
                processedRowLimit={lastRunRowLimit}
              />
            </ErrorBoundary>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center w-full flex-1 max-w-2xl min-h-[80vh]">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
              className="text-center mb-16"
            >
              <h1 className="text-5xl sm:text-6xl md:text-7xl font-thin tracking-tight text-neutral-900 dark:text-white mb-6">
                Relational Database
                <br />
                Intelligence Agent
              </h1>
              <p className="text-neutral-500 dark:text-neutral-400 text-lg font-light max-w-lg mx-auto">
                End-to-end schema extraction, quality scoring, and relationship
                inference powered by intelligence.
              </p>
            </motion.div>

            <AnimatePresence mode="wait">
              {ingestionState === "idle" && (
                <motion.div
                  key="idle"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="w-full space-y-4"
                >
                  <div className="bg-white/40 dark:bg-black/20 backdrop-blur-3xl border border-white/60 dark:border-white/5 rounded-[1.5rem] p-4">
                    <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                      <div>
                        <div className="text-sm font-medium text-neutral-800 dark:text-neutral-100">
                          Analysis Row Limit
                        </div>
                        <div className="text-xs text-neutral-500 dark:text-neutral-400">
                          Set to 0 for full scan, or choose up to 1,000,000 rows
                          per table.
                        </div>
                      </div>
                      <select
                        value={String(analysisRowLimit)}
                        onChange={(e) =>
                          setAnalysisRowLimit(Number(e.target.value))
                        }
                        className="px-3 py-2 rounded-xl bg-white/70 dark:bg-black/40 border border-black/10 dark:border-white/10 text-sm"
                      >
                        <option value="5000">5,000 rows</option>
                        <option value="50000">50,000 rows</option>
                        <option value="200000">200,000 rows</option>
                        <option value="1000000">1,000,000 rows</option>
                        <option value="0">Full scan (all rows)</option>
                      </select>
                    </div>
                  </div>

                  <label
                    className={clsx(
                      "group relative flex items-center justify-between p-6 rounded-[2rem] backdrop-blur-3xl border transition-all duration-500 cursor-pointer shadow-[0_8px_30px_rgba(0,0,0,0.02)]",
                      dragActive
                        ? "bg-white/60 dark:bg-white/10 border-[#0059B5] dark:border-[#60A5FA]"
                        : "bg-white/40 dark:bg-black/20 border-white/60 dark:border-white/5 hover:bg-white/60 dark:hover:bg-black/40",
                    )}
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                  >
                    <div className="flex items-center gap-5 pointer-events-none">
                      <div
                        className={clsx(
                          "w-14 h-14 rounded-2xl flex items-center justify-center transition-colors",
                          dragActive
                            ? "bg-[#0059B5]/10 dark:bg-[#60A5FA]/10"
                            : "bg-black/5 dark:bg-white/5",
                        )}
                      >
                        <FileUp
                          className={clsx(
                            "w-6 h-6 transition-colors",
                            dragActive
                              ? "text-[#0059B5] dark:text-[#60A5FA]"
                              : "text-neutral-600 dark:text-neutral-300",
                          )}
                        />
                      </div>
                      <div className="text-left">
                        <span className="block font-medium text-xl text-neutral-900 dark:text-neutral-100">
                          {dragActive ? "Drop to Upload" : "Upload Dataset"}
                        </span>
                        <span className="block font-light text-base text-neutral-500">
                          {dragActive
                            ? "Release files down here"
                            : "CSV bundles or SQLite files"}
                        </span>
                      </div>
                    </div>
                    <ArrowRight className="w-6 h-6 text-neutral-300 dark:text-neutral-600 group-hover:translate-x-1 group-hover:text-neutral-900 dark:group-hover:text-white transition-all duration-300 pointer-events-none" />
                    <input
                      type="file"
                      multiple
                      accept=".csv,.sqlite,.db,.sqlite3"
                      className="hidden"
                      onChange={handleFileUpload}
                    />
                  </label>

                  <button
                    onClick={() => setIngestionState("db_form")}
                    className="w-full group relative flex items-center justify-between p-6 rounded-[2rem] bg-white/40 dark:bg-black/20 backdrop-blur-3xl border border-white/60 dark:border-white/5 hover:bg-white/60 dark:hover:bg-black/40 transition-all duration-500 outline-none shadow-[0_8px_30px_rgba(0,0,0,0.02)]"
                  >
                    <div className="flex items-center gap-5 text-left">
                      <div className="w-14 h-14 rounded-2xl bg-black/5 dark:bg-white/5 flex items-center justify-center">
                        <Database className="w-6 h-6 text-neutral-600 dark:text-neutral-300 transition-colors" />
                      </div>
                      <div>
                        <span className="block font-medium text-xl text-neutral-900 dark:text-neutral-100">
                          Connect Database
                        </span>
                        <span className="block font-light text-base text-neutral-500">
                          PostgreSQL, MySQL, SQL Server
                        </span>
                      </div>
                    </div>
                    <ArrowRight className="w-6 h-6 text-neutral-300 dark:text-neutral-600 group-hover:translate-x-1 group-hover:text-neutral-900 dark:group-hover:text-white transition-all duration-300" />
                  </button>
                </motion.div>
              )}

              {ingestionState === "db_form" && (
                <motion.div
                  key="db_form"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="w-full max-w-2xl bg-white/50 dark:bg-black/30 backdrop-blur-3xl p-10 rounded-[2rem] border border-white/60 dark:border-white/5 shadow-[0_20px_40px_rgba(0,0,0,0.04)] text-left"
                >
                  <form onSubmit={handleDbSubmit} className="space-y-6">
                    <h3 className="font-light tracking-wide text-3xl text-neutral-900 dark:text-white mb-8">
                      Connection Details
                    </h3>

                    <div className="space-y-4">
                      <select
                        value={dbForm.db_type}
                        onChange={(e) =>
                          setDbForm({ ...dbForm, db_type: e.target.value })
                        }
                        className="w-full p-4 rounded-xl border-0 ring-1 ring-black/5 dark:ring-white/10 bg-white/50 dark:bg-black/50 text-base font-light focus:outline-none focus:ring-2 focus:ring-[#0059B5] dark:text-white transition-shadow"
                      >
                        <option value="postgresql">PostgreSQL</option>
                        <option value="mysql">MySQL</option>
                        <option value="sqlserver">SQL Server</option>
                        <option value="sqlite">SQLite (Local Path)</option>
                      </select>

                      <div className="grid grid-cols-3 gap-4">
                        <input
                          required
                          placeholder="Host"
                          value={dbForm.host}
                          onChange={(e) =>
                            setDbForm({ ...dbForm, host: e.target.value })
                          }
                          className="col-span-2 p-4 rounded-xl border-0 ring-1 ring-black/5 dark:ring-white/10 bg-white/50 dark:bg-black/50 text-base font-light focus:outline-none focus:ring-2 focus:ring-[#0059B5] dark:text-white transition-shadow"
                        />
                        <input
                          required
                          placeholder="Port"
                          value={dbForm.port}
                          onChange={(e) =>
                            setDbForm({ ...dbForm, port: e.target.value })
                          }
                          className="col-span-1 p-4 rounded-xl border-0 ring-1 ring-black/5 dark:ring-white/10 bg-white/50 dark:bg-black/50 text-base font-light focus:outline-none focus:ring-2 focus:ring-[#0059B5] dark:text-white transition-shadow"
                        />
                      </div>

                      <input
                        required
                        placeholder="Database Name"
                        value={dbForm.database}
                        onChange={(e) =>
                          setDbForm({ ...dbForm, database: e.target.value })
                        }
                        className="w-full p-4 rounded-xl border-0 ring-1 ring-black/5 dark:ring-white/10 bg-white/50 dark:bg-black/50 text-base font-light focus:outline-none focus:ring-2 focus:ring-[#0059B5] dark:text-white transition-shadow"
                      />

                      <div className="grid grid-cols-2 gap-4">
                        <input
                          required
                          placeholder="Username"
                          value={dbForm.username}
                          onChange={(e) =>
                            setDbForm({ ...dbForm, username: e.target.value })
                          }
                          className="p-4 rounded-xl border-0 ring-1 ring-black/5 dark:ring-white/10 bg-white/50 dark:bg-black/50 text-base font-light focus:outline-none focus:ring-2 focus:ring-[#0059B5] dark:text-white transition-shadow"
                        />
                        <PasswordField
                          value={dbForm.password}
                          onChange={(next) =>
                            setDbForm({ ...dbForm, password: next })
                          }
                          placeholder="Password"
                          visible={secretVisibility.dbPassword}
                          onToggle={() => toggleSecretVisibility("dbPassword")}
                          className="p-4 rounded-xl border-0 ring-1 ring-black/5 dark:ring-white/10 bg-white/50 dark:bg-black/50 text-base font-light focus:outline-none focus:ring-2 focus:ring-[#0059B5] dark:text-white transition-shadow"
                        />
                      </div>

                      <div className="space-y-2">
                        <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300">
                          Analysis Row Limit
                        </label>
                        <select
                          value={String(analysisRowLimit)}
                          onChange={(e) =>
                            setAnalysisRowLimit(Number(e.target.value))
                          }
                          className="w-full p-4 rounded-xl border-0 ring-1 ring-black/5 dark:ring-white/10 bg-white/50 dark:bg-black/50 text-base font-light focus:outline-none focus:ring-2 focus:ring-[#0059B5] dark:text-white transition-shadow"
                        >
                          <option value="5000">5,000 rows</option>
                          <option value="50000">50,000 rows</option>
                          <option value="200000">200,000 rows</option>
                          <option value="1000000">1,000,000 rows</option>
                          <option value="0">Full scan (all rows)</option>
                        </select>
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-8">
                      <button
                        type="button"
                        onClick={() => setIngestionState("idle")}
                        className="px-6 py-3 text-sm font-medium text-neutral-500 hover:text-neutral-900 dark:hover:text-white transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="text-base font-medium bg-gradient-to-br from-[#004289] to-[#0059B5] text-white px-8 py-4 rounded-2xl hover:opacity-90 transition-opacity shadow-[0_8px_20px_rgba(0,89,181,0.2)]"
                      >
                        Connect & Analyze
                      </button>
                    </div>
                  </form>
                </motion.div>
              )}

              {ingestionState === "processing" && (
                <motion.div
                  key="processing"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex flex-col items-center justify-center py-20 w-full"
                >
                  <div className="w-16 h-16 rounded-full bg-white/50 dark:bg-black/50 backdrop-blur-xl border border-white/60 dark:border-white/10 flex items-center justify-center shadow-lg relative overflow-hidden mb-6">
                    <Loader2 className="w-8 h-8 text-[#0059B5] animate-spin absolute" />
                  </div>
                  <p className="text-neutral-500 dark:text-neutral-400 text-xl font-light tracking-wide">
                    Synthesizing intelligence...
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </main>

      {appView === "home" && ingestionState === "idle" && (
        <LandingFeatures />
      )}

      <footer className="fixed bottom-6 left-1/2 -translate-x-1/2 text-center text-xs font-light tracking-[0.2em] text-neutral-400 dark:text-neutral-600 mix-blend-difference pointer-events-none">
        NEXUS INTELLIGENCE
      </footer>

      <AnimatePresence>
        {agentModalOpen && !agentAuthState.ok && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[70] bg-black/50 backdrop-blur-sm p-4 overflow-y-auto"
          >
            <motion.div
              initial={{ y: 30, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 20, opacity: 0 }}
              className="max-w-3xl mx-auto mt-20 bg-white/90 dark:bg-[#0f1116]/95 border border-white/50 dark:border-white/10 rounded-3xl shadow-2xl"
            >
              <div className="px-6 py-5 border-b border-black/10 dark:border-white/10 flex items-center justify-between">
                <div>
                  <h3 className="text-xl font-semibold text-neutral-900 dark:text-neutral-100">
                    {agentAuthState.ok ? "Agent Settings" : "Agent Login"}
                  </h3>
                  <p className="text-sm text-neutral-500 dark:text-neutral-400">
                    {agentAuthState.ok
                      ? "Configure inbox processing, model routing, and review activity logs."
                      : "Sign in with Firebase runtime credentials to activate the agent."}
                  </p>
                </div>
                <button
                  onClick={() => setAgentModalOpen(false)}
                  className="px-3 py-2 rounded-xl bg-black/5 dark:bg-white/10 text-sm font-medium"
                >
                  Close
                </button>
              </div>

              <div className="p-6 space-y-6">
                {agentError && (
                  <div className="p-3 rounded-xl bg-rose-500/10 text-rose-700 dark:text-rose-300 text-sm">
                    {agentError}
                  </div>
                )}
                {agentInfo && (
                  <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-sm">
                    {agentInfo}
                  </div>
                )}

                {!agentAuthState.ok && (
                  <>
                    <section className="space-y-4">
                      <h4 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
                        Firebase Runtime Credentials
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <input
                          value={agentForm.firebaseApiKey}
                          onChange={(e) =>
                            setAgentForm((prev) => ({
                              ...prev,
                              firebaseApiKey: e.target.value,
                            }))
                          }
                          placeholder="Firebase API Key"
                          className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                        <input
                          value={agentForm.firebaseAuthDomain}
                          onChange={(e) =>
                            setAgentForm((prev) => ({
                              ...prev,
                              firebaseAuthDomain: e.target.value,
                            }))
                          }
                          placeholder="Firebase Auth Domain"
                          className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                        <input
                          value={agentForm.firebaseProjectId}
                          onChange={(e) =>
                            setAgentForm((prev) => ({
                              ...prev,
                              firebaseProjectId: e.target.value,
                            }))
                          }
                          placeholder="Firebase Project ID"
                          className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                        <input
                          value={agentForm.firebaseStorageBucket}
                          onChange={(e) =>
                            setAgentForm((prev) => ({
                              ...prev,
                              firebaseStorageBucket: e.target.value,
                            }))
                          }
                          placeholder="Firebase Storage Bucket"
                          className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                      </div>
                    </section>

                    <section className="space-y-4">
                      <h4 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
                        Authenticate
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <input
                          value={agentForm.firebaseLoginEmail}
                          onChange={(e) =>
                            setAgentForm((prev) => ({
                              ...prev,
                              firebaseLoginEmail: e.target.value,
                            }))
                          }
                          placeholder="Firebase Email"
                          className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                        <PasswordField
                          value={agentForm.firebaseLoginPassword}
                          onChange={(next) =>
                            setAgentForm((prev) => ({
                              ...prev,
                              firebaseLoginPassword: next,
                            }))
                          }
                          placeholder="Firebase Password"
                          visible={secretVisibility.firebaseLoginPassword}
                          onToggle={() =>
                            toggleSecretVisibility("firebaseLoginPassword")
                          }
                          className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                      </div>
                      <button
                        onClick={handleAgentLogin}
                        disabled={agentWorking}
                        className="px-5 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold disabled:opacity-60"
                      >
                        {agentWorking ? "Authenticating..." : "Sign In Agent"}
                      </button>
                    </section>
                  </>
                )}

                {agentAuthState.ok && (
                  <section className="space-y-4">
                    <h4 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
                      Inbox Agent Settings
                    </h4>
                    <p className="text-sm text-emerald-700 dark:text-emerald-300">
                      Authenticated as {agentAuthState.email}
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <input
                        value={agentForm.agentEmail}
                        onChange={(e) =>
                          setAgentForm((prev) => ({
                            ...prev,
                            agentEmail: e.target.value,
                          }))
                        }
                        placeholder="Agent Gmail"
                        className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                      />
                      <PasswordField
                        value={agentForm.gmailAppPassword}
                        onChange={(next) =>
                          setAgentForm((prev) => ({
                            ...prev,
                            gmailAppPassword: next,
                          }))
                        }
                        placeholder="Gmail App Password"
                        visible={secretVisibility.gmailAppPassword}
                        onToggle={() =>
                          toggleSecretVisibility("gmailAppPassword")
                        }
                        className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                      />
                      <input
                        value={agentForm.imapHost}
                        onChange={(e) =>
                          setAgentForm((prev) => ({
                            ...prev,
                            imapHost: e.target.value,
                          }))
                        }
                        placeholder="IMAP Host"
                        className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                      />
                      <input
                        value={agentForm.smtpHost}
                        onChange={(e) =>
                          setAgentForm((prev) => ({
                            ...prev,
                            smtpHost: e.target.value,
                          }))
                        }
                        placeholder="SMTP Host"
                        className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                      />
                      <input
                        type="number"
                        min={1}
                        value={agentForm.smtpPort}
                        onChange={(e) =>
                          setAgentForm((prev) => ({
                            ...prev,
                            smtpPort: Number(e.target.value || 587),
                          }))
                        }
                        placeholder="SMTP Port"
                        className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                      />
                      <input
                        type="number"
                        min={0}
                        max={5}
                        value={agentForm.maxMessagesPerCycle}
                        onChange={(e) =>
                          setAgentForm((prev) => ({
                            ...prev,
                            maxMessagesPerCycle: clamp(
                              Number(e.target.value || 0),
                              0,
                              5,
                            ),
                          }))
                        }
                        placeholder="Max Emails Per Cycle"
                        className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                      />
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <select
                        value={agentForm.aiProvider}
                        onChange={(e) =>
                          setAgentForm((prev) => ({
                            ...prev,
                            aiProvider:
                              e.target.value === "gemini" ? "gemini" : "ollama",
                          }))
                        }
                        className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                      >
                        <option value="ollama">Local Ollama</option>
                        <option value="gemini">Gemini API</option>
                      </select>

                      {agentForm.aiProvider === "ollama" ? (
                        <button
                          onClick={() =>
                            loadOllamaModels(agentForm.ollamaEndpoint)
                          }
                          className="px-4 py-3 rounded-xl bg-black/5 dark:bg-white/10 border border-black/10 dark:border-white/10 text-sm font-medium"
                        >
                          Refresh Ollama Models
                        </button>
                      ) : (
                        <div />
                      )}
                    </div>

                    {agentForm.aiProvider === "ollama" ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <input
                          value={agentForm.ollamaEndpoint}
                          onChange={(e) =>
                            setAgentForm((prev) => ({
                              ...prev,
                              ollamaEndpoint: e.target.value,
                            }))
                          }
                          placeholder="Ollama Endpoint"
                          className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                        {ollamaModels.length > 0 ? (
                          <select
                            value={agentForm.ollamaModel}
                            onChange={(e) =>
                              setAgentForm((prev) => ({
                                ...prev,
                                ollamaModel: e.target.value,
                              }))
                            }
                            className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                          >
                            {ollamaModels.map((model) => (
                              <option key={model} value={model}>
                                {model}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <input
                            value={agentForm.ollamaModel}
                            onChange={(e) =>
                              setAgentForm((prev) => ({
                                ...prev,
                                ollamaModel: e.target.value,
                              }))
                            }
                            placeholder="Ollama Model"
                            className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                          />
                        )}
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <PasswordField
                          value={agentForm.geminiApiKey}
                          onChange={(next) =>
                            setAgentForm((prev) => ({
                              ...prev,
                              geminiApiKey: next,
                            }))
                          }
                          placeholder="Gemini API Key"
                          visible={secretVisibility.geminiApiKey}
                          onToggle={() =>
                            toggleSecretVisibility("geminiApiKey")
                          }
                          className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                        <input
                          value={agentForm.geminiModel}
                          onChange={(e) =>
                            setAgentForm((prev) => ({
                              ...prev,
                              geminiModel: e.target.value,
                            }))
                          }
                          placeholder="Gemini Model"
                          className="px-4 py-3 rounded-xl bg-white/60 dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                      </div>
                    )}

                    <div className="flex flex-wrap gap-3">
                      <button
                        onClick={handleProcessInboxOnce}
                        disabled={agentWorking || !hasAnalysis}
                        className="px-5 py-3 rounded-xl bg-[#0059B5] hover:bg-[#004289] text-white font-semibold disabled:opacity-60"
                      >
                        {agentWorking ? "Processing..." : "Process Inbox Once"}
                      </button>
                      {!hasAnalysis && (
                        <span className="text-sm text-amber-600 dark:text-amber-300 self-center">
                          Analyze data first to enable email processing.
                        </span>
                      )}
                    </div>
                  </section>
                )}

                {agentAuthState.ok && (
                  <section className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-base font-semibold text-neutral-900 dark:text-neutral-100">
                        Activity Logs
                      </h4>
                      <button
                        onClick={refreshAgentLogs}
                        className="px-3 py-2 text-xs rounded-lg bg-black/5 dark:bg-white/10"
                      >
                        Refresh
                      </button>
                    </div>
                    <div className="max-h-56 overflow-y-auto rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.03] dark:bg-white/[0.03] p-3">
                      {agentLogs.length === 0 ? (
                        <p className="text-sm text-neutral-500">No logs yet.</p>
                      ) : (
                        <div className="space-y-2">
                          {agentLogs.map((event, idx) => {
                            const ts = String(event.timestamp || "");
                            const level = String(
                              event.level || "INFO",
                            ).toUpperCase();
                            const msg = String(event.message || "");
                            const metadata = formatAgentLogMetadata(
                              event.metadata,
                            );
                            const levelTone =
                              level === "ERROR"
                                ? "text-rose-600 dark:text-rose-300"
                                : level === "WARNING"
                                  ? "text-amber-600 dark:text-amber-300"
                                  : level === "DEBUG"
                                    ? "text-sky-600 dark:text-sky-300"
                                    : "text-emerald-600 dark:text-emerald-300";
                            return (
                              <div
                                key={`${ts}-${idx}`}
                                className="rounded-lg border border-black/10 dark:border-white/10 bg-white/70 dark:bg-black/25 px-3 py-2 text-xs break-words"
                              >
                                <div className="flex items-center gap-2 mb-1 text-[11px]">
                                  <span className="text-neutral-500 dark:text-neutral-400">
                                    {new Date(
                                      ts || Date.now(),
                                    ).toLocaleString()}
                                  </span>
                                  <span
                                    className={clsx("font-semibold", levelTone)}
                                  >
                                    {level}
                                  </span>
                                </div>
                                <div className="text-neutral-800 dark:text-neutral-100">
                                  {msg}
                                </div>
                                {metadata ? (
                                  <div className="text-neutral-500 dark:text-neutral-400 mt-1">
                                    {metadata}
                                  </div>
                                ) : null}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </section>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      </div>
    </MotionConfig>
  );
}
