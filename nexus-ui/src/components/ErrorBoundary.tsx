import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error bound:', error, errorInfo);
    this.setState({ errorInfo });
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[50vh] p-8 m-8 rounded-3xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 font-mono shadow-2xl flex flex-col items-start overflow-hidden">
          <h1 className="text-2xl font-bold mb-4">React Error Boundary Tripped</h1>
          <p className="mb-4 text-sm font-semibold p-4 bg-rose-500/10 rounded-xl w-full">
            {this.state.error?.toString()}
          </p>
          <div className="w-full bg-black/5 dark:bg-black/50 p-4 rounded-xl overflow-auto text-xs whitespace-pre">
            {this.state.errorInfo?.componentStack}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
