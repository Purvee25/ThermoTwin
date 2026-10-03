import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ThermoTwin] Uncaught error:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="panel notice error" style={{ margin: '2rem auto', maxWidth: 480 }}>
          <strong>Something went wrong.</strong>
          <p style={{ marginTop: 8, fontSize: '0.85rem', opacity: 0.8 }}>
            {this.state.error.message}
          </p>
          <button
            type="button"
            className="btn"
            style={{ marginTop: 12 }}
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
