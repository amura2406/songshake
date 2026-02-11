/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "primary": "#af25f4",
        "background-light": "#f7f5f8",
        "background-dark": "#1c1022",
        "surface-dark": "#2a1b32",
        "surface-darker": "#150b1a",
      },
      fontFamily: {
        "display": ["Spline Sans", "sans-serif"]
      },
      boxShadow: {
        "neon": "0 0 10px rgba(175, 37, 244, 0.5)",
        "neon-strong": "0 0 20px rgba(175, 37, 244, 0.7)",
      }
    },
  },
  plugins: [],
}
