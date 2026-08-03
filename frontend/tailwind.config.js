/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],

  theme: {
    extend: {
      fontFamily: {
        display: ['"Playfair Display"', 'serif'],
        label: ['"JetBrains Mono"', 'monospace'],
        body: ['"Manrope"', 'sans-serif'],
      },

      colors: {
        background: "#0f0b08",

        primary: "#e9c349",

        secondary: "#d8ae52",

        surface: "#17110d",

        "surface-container-lowest": "#1b1410",

        "surface-container-highest": "#43352c",

        "on-surface": "#efe0d6",

        outline: "#9f835c",

        "outline-variant": "#4b3c2f",
      },

      boxShadow: {
        bronze: "0 0 30px rgba(233,195,73,.12)",
      },
    },
  },

  plugins: [],
}