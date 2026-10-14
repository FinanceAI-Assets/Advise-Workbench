import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "coral-black": "#0F0B0B",
        "tundora": "#4C4C4C",
        "light-gray": "#E5E5E5",
      },
      fontSize: {
        "2xs": "0.6875rem",
        "2xl": "1.75rem",
      },
    },
    /* Rounded corners (sampled from Figma design — small radius, not sharp/pill) */
    borderRadius: {
      none: "0px",
      sm: "4px",
      DEFAULT: "6px",
      md: "6px",
      lg: "8px",
      xl: "12px",
      "2xl": "16px",
      "3xl": "24px",
      full: "9999px",
    },
  },
  plugins: [],
};
export default config;
