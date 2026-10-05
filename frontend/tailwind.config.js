/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#FFFDF5",
        foreground: "#0A0A0A",
        brutal: {
          yellow: "#FFE600",
          pink: "#FF5C8D",
          green: "#00F0A8",
          blue: "#38BDF8",
          purple: "#A78BFA",
          orange: "#FB923C",
          dark: "#121212",
          paper: "#FDFBF7",
        },
      },
      boxShadow: {
        brutal: "4px 4px 0px 0px #000000",
        "brutal-sm": "2px 2px 0px 0px #000000",
        "brutal-lg": "6px 6px 0px 0px #000000",
        "brutal-xl": "8px 8px 0px 0px #000000",
      },
      borderWidth: {
        3: "3px",
      },
    },
  },
  plugins: [],
};

