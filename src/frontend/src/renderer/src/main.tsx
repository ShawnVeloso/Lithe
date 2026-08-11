import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { ErrorBoundary } from './ErrorBoundary'
import './index.css'

window.onerror = function (message, source, lineno, colno, error) {
  if (window.litheAPI) {
    const stack = error?.stack || `${source}:${lineno}:${colno}`
    window.litheAPI.logError(`[Uncaught] ${message}`, stack)
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
)
