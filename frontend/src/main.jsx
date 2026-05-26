import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.jsx'
import { FeedbackProvider } from './components/ui/FeedbackProvider'
import ErrorBoundary from './components/ErrorBoundary'
import { queryClient } from './lib/queryClient'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <FeedbackProvider>
          <App />
        </FeedbackProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)
