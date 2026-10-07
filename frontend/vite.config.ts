import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The board is served at http://localhost:5173 and calls the desk API directly
// at http://localhost:8000 (see src/api.ts). Start the API from hw5/ with:
//   uvicorn main:app --reload --port 8000
export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true, // fail loudly instead of drifting to 5174, which the API's CORS wouldn't allow
  },
})
