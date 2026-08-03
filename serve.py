"""Convenience launcher for the FastAPI web dashboard.

Usage:
    python serve.py               # default: http://localhost:8000
    python serve.py --port 9000   # custom port
    python serve.py --reload      # hot-reload for development
"""

import argparse
import sys

try:
    import uvicorn
except ImportError:
    print("uvicorn not installed. Run: pip install uvicorn", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the web dashboard")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable hot-reload (dev mode)")
    args = parser.parse_args()

    print(f"Dashboard → http://localhost:{args.port}")
    uvicorn.run(
        "src.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
