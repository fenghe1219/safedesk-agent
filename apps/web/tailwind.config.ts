import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "var(--sd-canvas)",
        surface: "var(--sd-surface)",
        subtle: "var(--sd-surface-subtle)",
        brand: {
          DEFAULT: "var(--sd-primary)",
          hover: "var(--sd-primary-hover)",
          soft: "var(--sd-primary-soft)",
          border: "var(--sd-primary-border)"
        },
        ink: {
          DEFAULT: "var(--sd-text)",
          secondary: "var(--sd-text-secondary)",
          tertiary: "var(--sd-text-tertiary)"
        },
        line: {
          DEFAULT: "var(--sd-border)",
          strong: "var(--sd-border-strong)"
        },
        warning: {
          DEFAULT: "var(--sd-warning)",
          soft: "var(--sd-warning-soft)"
        },
        danger: {
          DEFAULT: "var(--sd-danger)",
          soft: "var(--sd-danger-soft)"
        },
        success: {
          DEFAULT: "var(--sd-success)",
          soft: "var(--sd-success-soft)"
        },
        info: {
          DEFAULT: "var(--sd-info)",
          soft: "var(--sd-info-soft)"
        }
      },
      borderRadius: {
        control: "8px",
        card: "10px",
        overlay: "12px"
      },
      boxShadow: {
        card: "0 1px 2px rgba(23, 33, 31, 0.04)",
        overlay: "0 8px 24px rgba(23, 33, 31, 0.08)"
      },
      fontFamily: {
        sans: ["var(--sd-font-sans)"],
        mono: ["var(--sd-font-mono)"]
      }
    }
  },
  plugins: []
};

export default config;
