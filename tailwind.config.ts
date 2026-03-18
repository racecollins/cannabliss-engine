import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./charts/**/*.{ts,tsx}",
    "./data/**/*.{ts,tsx}",
    "./utils/**/*.{ts,tsx}",
    "./types/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#07110f",
        foreground: "#eff8f2",
        panel: "#0d1715",
        line: "#1f332e",
        muted: "#8fa8a0",
        accent: "#7ef0b2",
        "accent-soft": "#173227",
        gold: "#f2c66d",
        rose: "#f48ca9",
        sky: "#7bd6ff",
      },
      boxShadow: {
        panel: "0 20px 60px rgba(0, 0, 0, 0.28)",
      },
      backgroundImage: {
        halo:
          "radial-gradient(circle at top left, rgba(126, 240, 178, 0.18), transparent 32%), radial-gradient(circle at 82% 12%, rgba(123, 214, 255, 0.14), transparent 26%), linear-gradient(180deg, rgba(7, 17, 15, 0.96), rgba(5, 11, 10, 1))",
      },
      fontFamily: {
        sans: ["Avenir Next", "Segoe UI", "Helvetica Neue", "sans-serif"],
        display: ["Avenir Next", "Segoe UI", "Helvetica Neue", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
