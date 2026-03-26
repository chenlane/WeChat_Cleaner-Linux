import sys
import argparse

def main():
<<<<<<< HEAD
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
=======
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
>>>>>>> b1a2bad (feat: PyQt6 双视图（严格/近似）、Ctrl/Shift 多选、首尾采样并行哈希、硬链接识别、压缩包/PDF/Office近似模式、失败分类、README 更新)

if __name__ == "__main__":
    main()
