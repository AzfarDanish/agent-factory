import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      animation: {
        "walk-right": "walk-right 3s ease-in-out infinite",
        "walk-left": "walk-left 3s ease-in-out infinite",
        "walk-up": "walk-up 2.5s ease-in-out infinite",
        "walk-down": "walk-down 2.5s ease-in-out infinite",
        "bounce-gentle": "bounce-gentle 2s ease-in-out infinite",
        "chimney-smoke": "chimney-smoke 4s ease-out infinite",
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "day-cycle": "day-cycle 60s linear infinite",
      },
      keyframes: {
        "walk-right": {
          "0%, 100%": { transform: "translateX(0)" },
          "50%": { transform: "translateX(24px)" },
        },
        "walk-left": {
          "0%, 100%": { transform: "translateX(0)" },
          "50%": { transform: "translateX(-24px)" },
        },
        "walk-up": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-16px)" },
        },
        "walk-down": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(16px)" },
        },
        "bounce-gentle": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
        "chimney-smoke": {
          "0%": { opacity: "0.6", transform: "translateY(0) scale(1)" },
          "100%": { opacity: "0", transform: "translateY(-40px) scale(2)" },
        },
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 5px rgba(255,255,255,0.3)" },
          "50%": { boxShadow: "0 0 20px rgba(255,255,255,0.8)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
