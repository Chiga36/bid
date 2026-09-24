/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          // KPMG Blue (#00338D), the company's well-documented public brand color.
          50: "#e6ecf5",
          100: "#c0d0e8",
          500: "#00338D",
          600: "#00296e",
          700: "#001f54",
        },
      },
    },
  },
  plugins: [],
};
