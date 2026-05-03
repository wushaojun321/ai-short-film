/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // ── 设计 Token ──────────────────────────────────────
        bg:     "#141618",
        panel:  "#1B1D20",
        elev:   "#222529",
        soft:   "#2A2E32",
        line:   "rgba(226,232,240,0.13)",
        text:   "#F4F7F5",
        sub:    "#C9D3CF",
        muted:  { DEFAULT: "#98A6A1", bg: "#222529", foreground: "#C9D3CF" },

        // ── 品牌 ────────────────────────────────────────────
        brand:       "#34D399",
        "brand-soft":"rgba(52,211,153,0.13)",
        "brand-mid": "rgba(52,211,153,0.24)",
        primary:     "#10B981",
        "primary-soft": "rgba(16,185,129,0.13)",
        signal:      "#6EE7B7",
        "signal-soft":"rgba(110,231,183,0.12)",

        // ── 功能色 ──────────────────────────────────────────
        info:        "#0EA5E9",
        "info-soft": "rgba(14,165,233,0.12)",
        warn:        "#F59E0B",
        "warn-soft": "rgba(245,158,11,0.12)",
        danger:      "#EF4444",
        "danger-soft":"rgba(239,68,68,0.12)",
        success:     "#22C55E",
        "success-soft":"rgba(34,197,94,0.12)",

        // ── shadcn 兼容 ──────────────────────────────────────
        border:      "rgba(255,255,255,0.12)",
        input:       "rgba(255,255,255,0.14)",
        ring:        "#34D399",
        background:  "#141618",
        foreground:  "#F4F7F5",
        secondary:   { DEFAULT: "#222529", foreground: "#F4F7F5" },
        destructive: { DEFAULT: "#EF4444", foreground: "#FFFFFF" },
        accent:      { DEFAULT: "#2A2E32", foreground: "#F4F7F5" },
        popover:     { DEFAULT: "#1B1D20",  foreground: "#F4F7F5" },
        card:        { DEFAULT: "#1B1D20",  foreground: "#F4F7F5" },
      },
      fontFamily: {
        sans:  ['"Inter"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono:  ['"IBM Plex Mono"', "ui-monospace", "monospace"],
        serif: ['"Instrument Serif"', "Georgia", "serif"],
      },
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "1rem" }],
      },
      borderRadius: {
        lg: "0.5rem",
        md: "0.375rem",
        sm: "0.25rem",
        xl: "0.625rem",
        "2xl": "0.75rem",
      },
      boxShadow: {
        xs:    "0 1px 2px rgba(0,0,0,0.35)",
        sm:    "0 8px 20px rgba(0,0,0,0.28), 0 1px 0 rgba(255,255,255,0.04) inset",
        md:    "0 16px 36px rgba(0,0,0,0.34), 0 0 0 1px rgba(255,255,255,0.04)",
        lg:    "0 22px 48px rgba(0,0,0,0.34), 0 0 30px rgba(52,211,153,0.05)",
        brand: "0 0 0 3px rgba(52,211,153,0.16), 0 0 22px rgba(52,211,153,0.16)",
        card:  "0 14px 34px rgba(0,0,0,0.28)",
        "card-hover": "0 22px 48px rgba(0,0,0,0.36), 0 0 0 1px rgba(52,211,153,0.24), 0 0 26px rgba(52,211,153,0.08)",
        inner: "inset 0 1px 0 rgba(255,255,255,0.06)",
      },
      transitionDuration: {
        DEFAULT: "200ms",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-left": {
          from: { opacity: "0", transform: "translateX(-8px)" },
          to:   { opacity: "1", transform: "translateX(0)" },
        },
        shimmer: {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition:  "200% 0" },
        },
      },
      animation: {
        "fade-in":       "fade-in 0.2s ease-out",
        "slide-in-left": "slide-in-left 0.2s ease-out",
        shimmer:         "shimmer 1.5s infinite linear",
      },
    },
  },
  plugins: [],
};
