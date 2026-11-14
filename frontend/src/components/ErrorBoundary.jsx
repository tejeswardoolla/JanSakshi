import React from 'react'
import { AlertTriangle, RotateCcw, Home } from 'lucide-react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an unhandled error:', error, errorInfo)
    this.setState({ errorInfo })
  }

  handleReload = () => {
    window.location.reload()
  }

  handleGoHome = () => {
    window.location.href = '/authority'
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#090B10] text-[#F5F5F5] flex flex-col justify-center items-center px-4 py-12 relative overflow-hidden font-sans">
          {/* Ambient Lighting */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-red-500/10 rounded-full blur-[140px] pointer-events-none" />

          <div className="max-w-lg w-full bg-[#141722]/90 backdrop-blur-xl border border-red-500/20 rounded-3xl p-8 shadow-2xl relative z-10 text-center">
            <div className="w-14 h-14 rounded-2xl bg-red-500/15 border border-red-500/30 flex items-center justify-center text-red-400 mx-auto mb-4">
              <AlertTriangle className="w-7 h-7" />
            </div>

            <h1 className="text-xl font-bold text-[#F5F5F5]">Interface Error Recovered</h1>
            <p className="text-xs text-[#A1A1AA] mt-2">
              An unexpected component rendering issue occurred. Your municipal session remains safe and active.
            </p>

            {this.state.error?.message && (
              <div className="mt-4 p-3 rounded-xl bg-[#10131C] border border-white/[0.08] text-[11px] font-mono text-red-400/90 text-left overflow-x-auto">
                {this.state.error.message}
              </div>
            )}

            <div className="flex items-center justify-center gap-3 mt-6">
              <button
                onClick={this.handleReload}
                className="px-4 py-2.5 rounded-xl bg-[#F36B21] hover:bg-[#E05A10] text-white font-semibold text-xs flex items-center gap-2 cursor-pointer transition-all shadow-md"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Reload Page</span>
              </button>
              <button
                onClick={this.handleGoHome}
                className="px-4 py-2.5 rounded-xl bg-white/[0.08] hover:bg-white/[0.15] text-[#F5F5F5] font-semibold text-xs flex items-center gap-2 cursor-pointer transition-all border border-white/[0.08]"
              >
                <Home className="w-4 h-4" />
                <span>Operations Desk</span>
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

