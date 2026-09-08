import type { ReactNode } from 'react'
import Sidebar from './Sidebar'
import Header from './Header'

export default function MainLayout({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Header />
        <main style={{
          flex: 1, overflowY: 'auto',
          padding: '20px 24px',
          background: '#070d1a',
        }}>
          {children}
        </main>
      </div>
    </div>
  )
}
