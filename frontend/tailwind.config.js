/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["IBM Plex Sans", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      colors: {
        // Warm ink surfaces — deliberately not the stock zinc/slate AI palette.
        ink: {
          900: "#0e0d0b",
          800: "#161411",
          700: "#1d1a16",
          600: "#26221d",
        },
        line: "#292520",
        line2: "#3d372f",
        // NOTE: the key stays "cobalt" so existing class references keep working,
        // but the values are the brand bronze. Rename in a dedicated sweep only.
        cobalt: {
          400: "#d4a86a",
          500: "#c29a5b",
          600: "#a97f41",
          700: "#8a6634",
        },
      },
      letterSpacing: {
        overline: "0.18em",
      },
    },
  },
  plugins: [],
};
