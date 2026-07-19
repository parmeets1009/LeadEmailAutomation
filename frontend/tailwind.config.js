/** @type {import('tailwindcss').Config} */
// LIGHT professional theme in Novatide brand colours (teal #0F4C5C, ink #222).
// The scales below intentionally KEEP their legacy key names ("ink" surfaces,
// "cobalt" accent, inverted "zinc" text ramp) so every page restyles centrally
// with zero per-page edits. Rename only in a dedicated sweep.
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
        // Surfaces: 900 = page, 800 = panels, 700 = active/hover fills.
        ink: {
          900: "#f6f5f1",
          800: "#ffffff",
          700: "#e9efee",
          600: "#dde6e4",
        },
        line: "#e3e1d8",
        line2: "#c9c6ba",
        // Accent = Novatide deep teal.
        cobalt: {
          400: "#2e7a8c",
          500: "#17606f",
          600: "#0f4c5c",
          700: "#0b3a47",
        },
        // Inverted text ramp: low numbers = dark ink, high numbers = faint.
        zinc: {
          50: "#171a19",
          100: "#222222",
          200: "#363b39",
          300: "#4a504d",
          400: "#5b6360",
          500: "#757c78",
          600: "#9aa19d",
          700: "#c2c7c3",
          800: "#dcdfdb",
          900: "#eceeea",
        },
        // Status colours re-tuned for readability on light surfaces.
        emerald: {
          300: "#1d8a5e",
          400: "#177a52",
          500: "#106845",
        },
        amber: {
          300: "#8a6508",
          400: "#966d06",
          500: "#7f5c05",
        },
        red: {
          400: "#b23b32",
          500: "#9e332b",
        },
      },
      letterSpacing: {
        overline: "0.18em",
      },
    },
  },
  plugins: [],
};
