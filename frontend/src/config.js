const apiBase = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8003' : '')

export const config = {
  apiBase,
  endpoints: {
    apiRoot: `${apiBase}/api`,
  },
}

