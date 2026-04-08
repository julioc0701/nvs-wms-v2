const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8003'

export const config = {
  apiBase,
  endpoints: {
    apiRoot: `${apiBase}/api`,
  },
}

