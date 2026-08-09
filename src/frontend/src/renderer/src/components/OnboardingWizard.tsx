import { useState } from 'react'
import litheLogo from '../assets/lithe-mark-hero.svg'

function OnboardingWizard(): JSX.Element {
  const [apiKey, setApiKey] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!apiKey.trim()) return
    
    setIsSubmitting(true)
    try {
      await window.litheAPI.submitApiKey(apiKey.trim())
    } catch (err) {
      console.error(err)
      setIsSubmitting(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', backgroundColor: 'var(--bg-panel)' }}>
      <img src={litheLogo} alt="Lithe Logo" style={{ width: 120, marginBottom: '2rem' }} />
      <h1 style={{ color: 'var(--text-primary)', marginBottom: '1rem', fontWeight: 600 }}>Welcome to Lithe</h1>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem', textAlign: 'center', maxWidth: 400 }}>
        Lithe requires a Gemini API key to function. You can get one for free from Google AI Studio.
      </p>
      
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', width: 300 }}>
        <input 
          type="password"
          placeholder="GEMINI_API_KEY"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          style={{ 
            padding: '12px',
            backgroundColor: 'var(--bg-base)',
            border: '1px solid var(--border-light)',
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-mono)',
            marginBottom: '1rem',
            outline: 'none'
          }}
          disabled={isSubmitting}
        />
        <button 
          type="submit"
          disabled={isSubmitting || !apiKey.trim()}
          style={{
            padding: '12px',
            backgroundColor: 'var(--accent)',
            color: 'var(--bg-base)',
            border: 'none',
            fontWeight: 600,
            cursor: isSubmitting || !apiKey.trim() ? 'not-allowed' : 'pointer',
            opacity: isSubmitting || !apiKey.trim() ? 0.5 : 1
          }}
        >
          {isSubmitting ? 'Saving...' : 'Connect to Brain'}
        </button>
      </form>
    </div>
  )
}

export default OnboardingWizard
