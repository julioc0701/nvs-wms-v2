import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message || 'Erro inesperado' }
  }

  componentDidCatch(error) {
    // eslint-disable-next-line no-console
    console.error('ErrorBoundary:', error)
  }

  handleReload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
          <div className="max-w-md w-full rounded-2xl border border-red-200 bg-white p-6 text-center shadow-sm">
            <h1 className="text-xl font-bold text-red-700">Ocorreu um erro na interface</h1>
            <p className="text-sm text-slate-500 mt-2">{this.state.message}</p>
            <button
              onClick={this.handleReload}
              className="mt-5 px-4 py-2 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700"
            >
              Recarregar sistema
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

