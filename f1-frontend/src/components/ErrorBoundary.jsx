import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="status-screen error">
          UI error: {this.state.error.message} — reload to recover
        </div>
      )
    }
    return this.props.children
  }
}
