import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import EngineTwinLanding from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <EngineTwinLanding />
  </StrictMode>,
)
