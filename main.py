import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="WeChat Duplicate File Cleaner (Linux)")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode instead of GUI")
    parser.add_argument("path", nargs="?", help="Path to scan (only used in CLI mode)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (only used in CLI mode)")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto confirm (only used in CLI mode)")
    
    args = parser.parse_args()
    
    if args.cli:
        if not args.path:
            print("Error: path is required in CLI mode.")
            sys.exit(1)
            
        import cli
        # Overwrite sys.argv so cli.main parses correctly
        cli_args = [sys.argv[0], args.path]
        if args.dry_run:
            cli_args.append("--dry-run")
        if args.yes:
            cli_args.append("--yes")
            
        sys.argv = cli_args
        cli.main()
    else:
        try:
            import PyQt6
            import gui
            gui.run_app()
        except ImportError:
            print("Error: GUI dependencies (PyQt6) not installed.")
            print("Please run `pip install -r requirements.txt` or `pip install PyQt6`")
            print("Alternatively, run in CLI mode with `--cli` flag.")
            sys.exit(1)

if __name__ == "__main__":
    main()
