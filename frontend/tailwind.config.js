/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // High quality premium HSL palette
        brand: {
          50: 'hsl(220, 100%, 97%)',
          100: 'hsl(220, 100%, 92%)',
          200: 'hsl(220, 100%, 83%)',
          300: 'hsl(220, 100%, 70%)',
          400: 'hsl(220, 100%, 60%)',
          500: 'hsl(220, 100%, 50%)',
          600: 'hsl(220, 100%, 40%)',
          700: 'hsl(220, 100%, 30%)',
          800: 'hsl(220, 100%, 20%)',
          900: 'hsl(220, 100%, 10%)',
        },
        accent: {
          emerald: 'hsl(150, 80%, 40%)',
          amber: 'hsl(35, 90%, 50%)',
          crimson: 'hsl(350, 80%, 50%)',
        }
      },
      fontFamily: {
        sans: ['Outfit', 'Inter', 'system-ui', 'sans-serif'],
      },
      backdropBlur: {
        xs: '2px',
      }
    },
  },
  plugins: [],
}
