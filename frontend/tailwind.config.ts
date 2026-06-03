import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#001836",
          container: "#002d5b",
          fixed: "#d5e3ff",
        },
        secondary: {
          DEFAULT: "#275fa5",
          container: "#81b2fe",
        },
        surface: {
          DEFAULT: "#f7f9fb",
          container: "#eceef0",
          "container-low": "#f2f4f6",
          glass: "rgba(255, 255, 255, 0.70)",
        },
        "on-surface": {
          DEFAULT: "#191c1e",
          variant: "#43474f",
        },
        outline: {
          DEFAULT: "#737780",
          variant: "#c3c6d0",
        },
        "data-blue": "#0066cc",
        "nca-red": "#e31937",
        "nca-gold": "#ffd100",
        success: {
          DEFAULT: "#1f7a4d",
          soft: "#e5f4eb",
        },
        warning: {
          soft: "#fff3bf",
        },
        critical: {
          soft: "#ffe8e8",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["Inter", "system-ui", "sans-serif"],
      },
      fontSize: {
        "display-lg": ["48px", { lineHeight: "56px", letterSpacing: "-0.02em", fontWeight: "700" }],
        "headline-lg": ["32px", { lineHeight: "40px", letterSpacing: "-0.01em", fontWeight: "600" }],
        "headline-md": ["24px", { lineHeight: "32px", fontWeight: "600" }],
        "headline-sm": ["20px", { lineHeight: "28px", fontWeight: "600" }],
        "body-lg": ["18px", { lineHeight: "28px", fontWeight: "400" }],
        "body-md": ["16px", { lineHeight: "24px", fontWeight: "400" }],
        "body-sm": ["14px", { lineHeight: "20px", fontWeight: "400" }],
        "label-md": ["12px", { lineHeight: "16px", letterSpacing: "0.05em", fontWeight: "600" }],
        "data-mono": ["14px", { lineHeight: "20px", letterSpacing: "-0.01em", fontWeight: "500" }],
      },
      borderRadius: {
        sm: "8px",
        DEFAULT: "8px",
        md: "12px",
        lg: "16px",
        xl: "24px",
      },
      boxShadow: {
        card: "0 16px 42px rgba(0, 45, 91, 0.10)",
        glass: "0 8px 32px rgba(0, 45, 91, 0.08)",
        modal: "0 24px 64px rgba(0, 45, 91, 0.16)",
      },
      spacing: {
        "4.5": "18px",
        "18": "72px",
        "76": "304px",
      },
      maxWidth: {
        container: "1440px",
      },
      backdropBlur: {
        glass: "12px",
      },
    },
  },
  plugins: [],
};

export default config;
