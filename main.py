import sys
import argparse

def main():
    if "--cli" in sys.argv[1:]:
        idx = sys.argv.index("--cli")
        import cli
        sys.argv = [sys.argv[0]] + sys.argv[idx + 1 :]
        cli.main()
        return

    parser = argparse.ArgumentParser(description="WeChat Duplicate File Cleaner (Linux)")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode instead of GUI")
    args = parser.parse_args()
    if args.cli:
        print("Error: use `python3 main.py --cli <path> [options]` for command-line mode.")
        sys.exit(1)

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
