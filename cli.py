import argparse
import os
import stat
from collections import defaultdict
from typing import Optional, Tuple
from send2trash import send2trash
from core import DuplicateScanner, ScanOptions, effective_savings

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

def classify_error(err: Exception) -> str:
    if isinstance(err, FileNotFoundError):
        return "not_found"
    if isinstance(err, PermissionError):
        return "permission"
    if isinstance(err, OSError):
        return f"oserror_{getattr(err, 'errno', 'unknown')}"
    return "unknown"

def suggest_for_category(category: str) -> str:
    if category == "permission":
        return "建议检查目录写权限/文件不可变属性（lsattr）/属主，或关闭微信占用后重试"
    if category == "not_found":
        return "文件可能已被移动或删除，重新扫描即可"
    if category.startswith("oserror_"):
        return "建议查看错误码含义，常见为权限或跨文件系统限制"
    return "建议打开 GUI 右键定位文件所在目录后手工检查"

def replace_with_hardlink(keep_path: str, target_path: str) -> Tuple[bool, Optional[Exception]]:
    try:
        if os.path.samefile(keep_path, target_path):
            return True, None
        st_keep = os.stat(keep_path)
        st_target = os.stat(target_path)
        if st_keep.st_dev != st_target.st_dev:
            return False, OSError("Hardlink requires same filesystem")
        tmp = target_path + ".wxcleaner_tmp_link"
        if os.path.exists(tmp):
            os.remove(tmp)
        os.link(keep_path, tmp)
        ok, err = move_to_trash(target_path)
        if not ok:
            os.remove(tmp)
            return False, err
        os.replace(tmp, target_path)
        return True, None
    except Exception as e:
        return False, e

def replace_with_symlink(keep_path: str, target_path: str) -> Tuple[bool, Optional[Exception]]:
    try:
        if os.path.samefile(keep_path, target_path):
            return True, None
        tmp = target_path + ".wxcleaner_tmp_link"
        if os.path.lexists(tmp):
            os.remove(tmp)
        rel = os.path.relpath(keep_path, os.path.dirname(target_path))
        os.symlink(rel, tmp)
        ok, err = move_to_trash(target_path)
        if not ok:
            os.remove(tmp)
            return False, err
        os.replace(tmp, target_path)
        return True, None
    except Exception as e:
        return False, e

def main():
    parser = argparse.ArgumentParser(description="Linux WeChat Duplicate File Cleaner")
    parser.add_argument("path", help="Path to WeChat storage directory to scan")
    parser.add_argument("--dry-run", action="store_true", help="Just print what would be deleted, don't actually delete")
    parser.add_argument("--yes", "-y", action="store_true", help="Don't prompt for confirmation before deleting")
    parser.add_argument("--perceptual-images", action="store_true", help="Enable perceptual image grouping (report only by default)")
    parser.add_argument("--normalize-pdf", action="store_true", help="Enable PDF metadata-normalized grouping (report only by default)")
    parser.add_argument("--normalize-office", action="store_true", help="Enable Office structure-normalized grouping (report only by default)")
    parser.add_argument("--normalize-archive", action="store_true", help="Enable archive normalized grouping (zip/tar; report only by default)")
    parser.add_argument("--replace-hardlink", action="store_true", help="Replace duplicates with hardlinks instead of moving to trash")
    parser.add_argument("--replace-symlink", action="store_true", help="Replace duplicates with symlinks instead of moving to trash")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.path):
        print(f"Error: Path {args.path} does not exist.")
        return
        
    print(f"Scanning directory: {args.path}...")
    if args.replace_hardlink and args.replace_symlink:
        print("Error: --replace-hardlink and --replace-symlink cannot be used together.")
        return

    opts = ScanOptions(
        enable_image_perceptual=bool(args.perceptual_images),
        enable_pdf_normalize=bool(args.normalize_pdf),
        enable_office_normalize=bool(args.normalize_office),
        enable_archive_normalize=bool(args.normalize_archive),
    )
    scanner = DuplicateScanner(args.path, options=opts)
    
    def progress(step, total, msg):
        print(f"[{step}/{total}] {msg}")
        
    result = scanner.scan(progress)
    
    exact_groups = [g for g in result.groups if g.kind == "exact"]
    near_groups = [g for g in result.groups if g.kind != "exact"]

    if not exact_groups and not near_groups:
        print("No duplicate files found.")
        return
        
    total_saved = 0
    to_delete = []
    
    for group in exact_groups:
        keep_file = group.keep_path
        delete_files = [p for p in group.paths if p != keep_file]
        
        print(f"\nGroup {group.group_id}: (Keep: {keep_file})")
        for f in delete_files:
            print(f"  -> Delete: {f}")
            to_delete.append(f)

    total_saved = effective_savings(result.file_info, to_delete)
            
    print(f"\nFound {len(to_delete)} duplicate files.")
    print(f"Total space that can be saved: {total_saved / 1024 / 1024:.2f} MB")

    if near_groups:
        print(f"\nFound {len(near_groups)} near-duplicate groups (not auto-deleted):")
        for g in near_groups[:20]:
            print(f"  Near {g.kind} Group {g.group_id}: {len(g.paths)} files, sample keep: {g.keep_path}")
    
    if args.dry_run:
        print("Dry run mode. Exiting without deleting.")
        return
        
    if not args.yes:
        if args.replace_hardlink:
            confirm = input("Do you want to replace duplicates with hardlinks? (y/N): ")
        elif args.replace_symlink:
            confirm = input("Do you want to replace duplicates with symlinks? (y/N): ")
        else:
            confirm = input("Do you want to move these files to the trash? (y/N): ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return
            
    if args.replace_hardlink:
        print("Replacing files with hardlinks...")
    elif args.replace_symlink:
        print("Replacing files with symlinks...")
    else:
        print("Moving files to trash...")
    deleted_count = 0
    failed: Dict[str, int] = defaultdict(int)

    keep_for_path: Dict[str, str] = {}
    for g in exact_groups:
        for p in g.deletable_paths():
            keep_for_path[p] = g.keep_path

    for file_path in to_delete:
        if args.replace_hardlink:
            ok, err = replace_with_hardlink(keep_for_path[file_path], file_path)
        elif args.replace_symlink:
            ok, err = replace_with_symlink(keep_for_path[file_path], file_path)
        else:
            ok, err = move_to_trash(file_path)
        if ok:
            deleted_count += 1
        else:
            cat = classify_error(err) if isinstance(err, Exception) else "unknown"
            failed[cat] += 1
            print(f"Failed: {file_path}: {err}")
            
    if failed:
        print("\nFailure summary:")
        for cat, cnt in sorted(failed.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {cat}: {cnt} ({suggest_for_category(cat)})")

    if args.replace_hardlink:
        print(f"\nSuccessfully replaced {deleted_count} files. Failed: {sum(failed.values())}.")
    elif args.replace_symlink:
        print(f"\nSuccessfully replaced {deleted_count} files. Failed: {sum(failed.values())}.")
    else:
        print(f"\nSuccessfully moved {deleted_count} files to the trash. Failed: {sum(failed.values())}.")

if __name__ == "__main__":
    main()
