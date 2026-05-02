/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        gh: {
          bg:     '#0d1117',
          panel:  '#161b22',
          border: '#30363d',
          text:   '#c9d1d9',
          muted:  '#8b949e',
          blue:   '#58a6ff',
          green:  '#56d364',
          orange: '#ffa657',
          red:    '#f85149',
          purple: '#d2a8ff',
        },
      },
    },
  },
  plugins: [],
};
