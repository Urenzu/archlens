"""CLI entry point — analyze a repo or start the server."""

from __future__ import annotations

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(prog="archlens", description="ArchLens code analyzer")
    sub = parser.add_subparsers(dest="command")

    # analyze subcommand — print JSON to stdout
    analyze_p = sub.add_parser("analyze", help="Analyze a repository and print JSON")
    analyze_p.add_argument("path", help="Path to the repository")

    # serve subcommand — start the API server
    serve_p = sub.add_parser("serve", help="Start the API server")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8000)
    serve_p.add_argument("--reload", action="store_true")

    args = parser.parse_args()

    if args.command == "analyze":
        from .analyze import analyze_repo

        result = analyze_repo(args.path)
        print(result.to_json())

    elif args.command == "serve":
        import uvicorn

        uvicorn.run(
            "archlens.server:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
