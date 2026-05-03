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
        bg:     "#FFFFFF",
        panel:  "#FFFFFF",
        elev:   "#F8FAFC",
        soft:   "#F1F5F9",
        line:   "#E2E8F0",
        text:   "#0F172A",
        sub:    "#475569",
        muted:  { DEFAULT: "#94A3B8", bg: "#F8FAFC", foreground: "#64748B" },

        // ── 品牌 ────────────────────────────────────────────
        brand:       "#059669",          // 绿色 CTA（专业感）
        "brand-soft":"rgba(5,150,105,0.10)",
        "brand-mid": "rgba(5,150,105,0.20)",
        primary:     "#1E3A5F",          // 深海蓝（标题/主色）
        "primary-soft": "rgba(30,58,95,0.08)",

        // ── 功能色 ──────────────────────────────────────────
        warn:        "#D97706",
        "warn-soft": "rgba(217,119,6,0.10)",
        danger:      "#DC2626",
        "danger-soft":"rgba(220,38,38,0.10)",
        success:     "#059669",
        "success-soft":"rgba(5,150,105,0.10)",

        // ── shadcn 兼容 ──────────────────────────────────────
        border:      "#E2E8F0",
        input:       "#E2E8F0",
        ring:        "#059669",
        background:  "#FFFFFF",
        foreground:  "#0F172A",
        secondary:   { DEFAULT: "#F1F5F9", foreground: "#0F172A" },
        destructive: { DEFAULT: "#DC2626", foreground: "#FFFFFF" },
        accent:      { DEFAULT: "#F1F5F9", foreground: "#0F172A" },
        popover:     { DEFAULT: "#FFFFFF",  foreground: "#0F172A" },
        card:        { DEFAULT: "#FFFFFF",  foreground: "#0F172A" },
      },
      fontFamily: {
        sans:  ['"Plus Jakarta Sans"', '"IBM Plex Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono:  ['"IBM Plex Mono"', "ui-monospace", "monospace"],
        serif: ['"Instrument Serif"', "Georgia", "serif"],
      },
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "1rem" }],
      },
      borderRadius: {
        lg: "0.75rem",
        md: "0.5rem",
        sm: "0.375rem",
        xl: "1rem",
        "2xl": "1.25rem",
      },
      boxShadow: {
        xs:    "0 1px 2px rgba(15,23,42,0.06)",
        sm:    "0 1px 3px rgba(15,23,42,0.08), 0 1px 2px rgba(15,23,42,0.06)",
        md:    "0 4px 8px rgba(15,23,42,0.08), 0 2px 4px rgba(15,23,42,0.05)",
        lg:    "0 8px 24px rgba(15,23,42,0.10), 0 2px 8px rgba(15,23,42,0.06)",
        brand: "0 0 0 3px rgba(5,150,105,0.20)",
        card:  "0 10px 30px rgba(15,23,42,0.08)",
        "card-hover": "0 16px 42px rgba(15,23,42,0.12), 0 4px 12px rgba(15,23,42,0.06)",
        inner: "inset 0 1px 2px rgba(15,23,42,0.06)",
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
