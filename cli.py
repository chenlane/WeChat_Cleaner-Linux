import argparse
import os
import stat
from send2trash import send2trash
from core import DuplicateScanner

def move_to_trash(filepath):
    try:
        send2trash(filepath)
        return True, None
    except PermissionError as e:
        try:
            current_mode = os.stat(filepath).st_mode
            os.chmod(filepath, current_mode | stat.S_IWUSR)
            send2trash(filepath)
            return True, None
        except Exception as e2:
            return False, e2
    except Exception as e:
        return False, e

def main():
    parser = argparse.ArgumentParser(description="Linux WeChat Duplicate File Cleaner")
    parser.add_argument("path", help="Path to WeChat storage directory to scan")
    parser.add_argument("--dry-run", action="store_true", help="Just print what would be deleted, don't actually delete")
    parser.add_argument("--yes", "-y", action="store_true", help="Don't prompt for confirmation before deleting")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.path):
        print(f"Error: Path {args.path} does not exist.")
        return
        
    print(f"Scanning directory: {args.path}...")
    scanner = DuplicateScanner(args.path)
    
    def progress(step, total, msg):
        print(f"[{step}/{total}] {msg}")
        
    duplicates = scanner.scan(progress)
    
    if not duplicates:
        print("No duplicate files found.")
        return
        
    total_saved = 0
    to_delete = []
    
    for group in duplicates:
        keep_file = group[0]
        delete_files = group[1:]
        
        # calculate size saved
        size = os.path.getsize(keep_file)
        total_saved += size * len(delete_files)
        
        print(f"\nGroup: (Keep: {keep_file})")
        for f in delete_files:
            print(f"  -> Delete: {f}")
            to_delete.append(f)
            
    print(f"\nFound {len(to_delete)} duplicate files.")
    print(f"Total space that can be saved: {total_saved / 1024 / 1024:.2f} MB")
    
    if args.dry_run:
        print("Dry run mode. Exiting without deleting.")
        return
        
    if not args.yes:
        confirm = input("Do you want to move these files to the trash? (y/N): ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return
            
    print("Moving files to trash...")
    deleted_count = 0
    failed_count = 0
    for file_path in to_delete:
        ok, err = move_to_trash(file_path)
        if ok:
            deleted_count += 1
        else:
            failed_count += 1
            print(f"Failed to delete {file_path}: {err}")
            
    print(f"Successfully moved {deleted_count} files to the trash. Failed: {failed_count}.")

if __name__ == "__main__":
    main()
