import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#0A0E14",
        panel: "#10151E",
        panel2: "#161D29",
        edge: "#243043",
        mono: "#7C8FA6",
        accent: { blue: "#3B82F6", amber: "#F59E0B", red: "#EF4444", green: "#10B981" },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        crisis: "0 0 80px 10px rgba(239, 68, 68, 0.22)",
        panel: "0 4px 24px rgba(0, 0, 0, 0.35)",
      },
    },
  },
  plugins: [],
} satisfies Config;
