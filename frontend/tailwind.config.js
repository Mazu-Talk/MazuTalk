/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      // 아동 친화형 팔레트 — 부드럽고 자극이 낮은 색상 (NFR-004 낮은 자극)
      colors: {
        brand: {
          50: '#eef7ff',
          100: '#d9ecff',
          200: '#bcdcff',
          300: '#8ec6ff',
          400: '#59a6ff',
          500: '#3385f6',
          600: '#2167db',
          700: '#1b53b1',
          800: '#1c478c',
          900: '#1c3e72',
        },
        // 감정별 색상 (FD-03 / Emotion Analysis)
        emotion: {
          happy: '#ffd166',
          neutral: '#c7d0db',
          anxious: '#a0c4ff',
          confused: '#cdb4f6',
          passive: '#bfc8d6',
          shy: '#ffc6e0',
          frustrated: '#ff9aa2',
        },
        cream: '#fffaf0',
      },
      fontFamily: {
        round: ['"Gowun Dodum"', '"Apple SD Gothic Neo"', '"Malgun Gothic"', 'sans-serif'],
      },
      borderRadius: {
        '2xl': '1.25rem',
        '3xl': '1.75rem',
        blob: '2.5rem',
      },
      boxShadow: {
        soft: '0 10px 30px -12px rgba(33, 103, 219, 0.35)',
        card: '0 8px 24px -10px rgba(28, 62, 114, 0.25)',
      },
      keyframes: {
        'bounce-soft': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(0.95)', opacity: '0.7' },
          '70%': { transform: 'scale(1.3)', opacity: '0' },
          '100%': { opacity: '0' },
        },
        'pop-in': {
          '0%': { transform: 'scale(0.8)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        'wave': {
          '0%, 100%': { transform: 'scaleY(0.4)' },
          '50%': { transform: 'scaleY(1)' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
      },
      animation: {
        'bounce-soft': 'bounce-soft 1.6s ease-in-out infinite',
        'pulse-ring': 'pulse-ring 1.5s ease-out infinite',
        'pop-in': 'pop-in 0.3s ease-out',
        'wave': 'wave 1s ease-in-out infinite',
        'float': 'float 4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
