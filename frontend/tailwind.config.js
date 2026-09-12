/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        teal: {
          DEFAULT: "#0d9488",
          50: "#f0fdfa",
          100: "#ccfbf1",
          600: "#0d9488",
          700: "#0f766e",
          800: "#115e59",
        },
        wein: {
          DEFAULT: "#7b2d42",
          50: "#fdf2f5",
          100: "#fce7ec",
          500: "#b45372",
          600: "#7b2d42",
          700: "#5e1f30",
        },
        salbei: {
          DEFAULT: "#7a9e7e",
          50: "#f3f8f3",
          100: "#e2efe3",
          500: "#7a9e7e",
          600: "#5f8463",
          700: "#4a6b4e",
        },
      },
    },
  },
  plugins: [],
};
