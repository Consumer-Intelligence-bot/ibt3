import { Component } from 'react';
import { FONT, COLORS } from '../../utils/brandConstants';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: 40,
          fontFamily: FONT.family,
          textAlign: 'center',
          maxWidth: 600,
          margin: '80px auto',
        }}>
          <h2 style={{ color: COLORS.red, marginBottom: 16 }}>Something went wrong</h2>
          <p style={{ color: '#666', fontSize: 14, marginBottom: 24 }}>
            An unexpected error occurred. Please refresh the page to try again.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '8px 24px',
              backgroundColor: COLORS.magenta,
              color: '#fff',
              border: 'none',
              borderRadius: 4,
              fontSize: 14,
              fontFamily: FONT.family,
              cursor: 'pointer',
            }}
          >
            Refresh Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
