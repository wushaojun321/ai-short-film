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
        bg:     "#09090B",
        panel:  "#111113",
        elev:   "#18181B",
        soft:   "#232326",
        line:   "rgba(255,255,255,0.12)",
        text:   "#F8FAFC",
        sub:    "#CBD5E1",
        muted:  { DEFAULT: "#94A3B8", bg: "#18181B", foreground: "#CBD5E1" },

        // ── 品牌 ────────────────────────────────────────────
        brand:       "#EF233C",
        "brand-soft":"rgba(239,35,60,0.14)",
        "brand-mid": "rgba(239,35,60,0.28)",
        primary:     "#EF233C",
        "primary-soft": "rgba(239,35,60,0.14)",
        signal:      "#FF4D5E",
        "signal-soft":"rgba(255,77,94,0.14)",

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
        ring:        "#EF233C",
        background:  "#09090B",
        foreground:  "#F8FAFC",
        secondary:   { DEFAULT: "#18181B", foreground: "#F8FAFC" },
        destructive: { DEFAULT: "#EF4444", foreground: "#FFFFFF" },
        accent:      { DEFAULT: "#232326", foreground: "#F8FAFC" },
        popover:     { DEFAULT: "#111113",  foreground: "#F8FAFC" },
        card:        { DEFAULT: "#111113",  foreground: "#F8FAFC" },
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
        lg:    "0 24px 60px rgba(0,0,0,0.42), 0 0 38px rgba(239,35,60,0.08)",
        brand: "0 0 0 3px rgba(239,35,60,0.20), 0 0 26px rgba(239,35,60,0.22)",
        card:  "0 18px 44px rgba(0,0,0,0.34)",
        "card-hover": "0 28px 68px rgba(0,0,0,0.46), 0 0 0 1px rgba(239,35,60,0.30), 0 0 36px rgba(239,35,60,0.12)",
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
