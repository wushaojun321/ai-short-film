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
        bg:     "#FAFAFA",
        panel:  "#FFFFFF",
        elev:   "#FAFAFA",
        soft:   "#F5F5F5",
        line:   "#D4D4D4",
        text:   "#171717",
        sub:    "#525252",
        muted:  { DEFAULT: "#737373", bg: "#F5F5F5", foreground: "#525252" },

        // ── 品牌 ────────────────────────────────────────────
        brand:       "#000000",
        "brand-soft":"rgba(0,0,0,0.06)",
        "brand-mid": "rgba(0,0,0,0.14)",
        primary:     "#000000",
        "primary-soft": "rgba(0,0,0,0.06)",
        signal:      "#262626",
        "signal-soft":"rgba(38,38,38,0.08)",

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
        border:      "#D4D4D4",
        input:       "#D4D4D4",
        ring:        "#000000",
        background:  "#FAFAFA",
        foreground:  "#171717",
        secondary:   { DEFAULT: "#262626", foreground: "#FFFFFF" },
        destructive: { DEFAULT: "#EF4444", foreground: "#FFFFFF" },
        accent:      { DEFAULT: "#F5F5F5", foreground: "#171717" },
        popover:     { DEFAULT: "#FFFFFF",  foreground: "#171717" },
        card:        { DEFAULT: "#FFFFFF",  foreground: "#171717" },
      },
      fontFamily: {
        sans:  ['"Lato"', "ui-sans-serif", "system-ui", "sans-serif"],
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
        xs:    "0 1px 2px rgba(23,23,23,0.05)",
        sm:    "0 1px 3px rgba(23,23,23,0.08), 0 1px 2px rgba(23,23,23,0.04)",
        md:    "0 6px 16px rgba(23,23,23,0.08), 0 2px 5px rgba(23,23,23,0.04)",
        lg:    "0 14px 32px rgba(23,23,23,0.12), 0 4px 10px rgba(23,23,23,0.06)",
        brand: "0 0 0 3px rgba(0,0,0,0.12)",
        card:  "0 12px 28px rgba(23,23,23,0.08)",
        "card-hover": "0 18px 38px rgba(23,23,23,0.12), 0 0 0 1px rgba(0,0,0,0.08)",
        inner: "inset 0 1px 2px rgba(23,23,23,0.04)",
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
