import os
import hashlib
from collections import defaultdict
import re

def get_file_size(filepath):
    try:
        return os.path.getsize(filepath)
    except OSError:
        return -1

def get_file_header_hash(filepath, chunk_size=4096):
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(chunk_size)
            return hashlib.md5(chunk).hexdigest()
    except OSError:
        return None

def get_file_full_hash(filepath, chunk_size=8192):
    try:
        md5 = hashlib.md5()
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                md5.update(chunk)
        return md5.hexdigest()
    except OSError:
        return None

def score_file_for_keeping(filepath):
    """
    Score a file to determine if it should be kept.
    We return a tuple where lower values indicate higher priority to keep.
    Priority:
    1. Does NOT have suffix like (1), (2) -> 0 for no suffix, 1 for suffix
    2. Modification time -> LATEST files (larger timestamp) kept first.
       Why? If content is same (which is the case for duplicates), the most recently 
       modified one is often the most "up-to-date" version user worked on.
    3. Filename length -> shorter names kept first (if mtime is same)
    """
    filename = os.path.basename(filepath)
    
    # 1. Penalize files with (1), (2), etc.
    has_suffix = 1 if re.search(r'\(\d+\)', filename) else 0
    
    # 2. Modification time
    try:
        mtime = os.path.getmtime(filepath)
    except OSError:
        mtime = 0 # push to end if error
        
    # Use negative mtime to prioritize larger (later) timestamps
    
    # 3. Filename length
    name_len = len(filename)
    
    return (has_suffix, -mtime, name_len)

class DuplicateScanner:
    def __init__(self, directory):
        self.directory = directory
        
    def scan(self, progress_callback=None):
        """
        Scan directory and return a list of duplicate file groups.
        progress_callback(current_step, total_steps, message)
        """
        if progress_callback:
            progress_callback(0, 4, "正在收集所有文件...")
            
        # Step 1: Collect all files and group by size
        size_dict = defaultdict(list)
        for root, _, files in os.walk(self.directory):
            for file in files:
                filepath = os.path.join(root, file)
                size = get_file_size(filepath)
                if size > 0: # Ignore empty files
                    size_dict[size].append(filepath)
                    
        # Filter groups with > 1 files
        candidates_by_size = {size: paths for size, paths in size_dict.items() if len(paths) > 1}
        
        if progress_callback:
            progress_callback(1, 4, f"根据大小找到 {len(candidates_by_size)} 组可能重复的文件，正在计算头部哈希...")
            
        # Step 2: Group by header hash
        header_dict = defaultdict(list)
        for size, paths in candidates_by_size.items():
            for filepath in paths:
                header_hash = get_file_header_hash(filepath)
                if header_hash:
                    # use size + header_hash to prevent hash collision between different sizes
                    key = f"{size}_{header_hash}"
                    header_dict[key].append(filepath)
                    
        candidates_by_header = {key: paths for key, paths in header_dict.items() if len(paths) > 1}
        
        if progress_callback:
            progress_callback(2, 4, f"根据头部哈希找到 {len(candidates_by_header)} 组可能重复的文件，正在计算全量哈希...")
            
        # Step 3: Group by full hash
        full_dict = defaultdict(list)
        total_files = sum(len(paths) for paths in candidates_by_header.values())
        processed = 0
        
        for key, paths in candidates_by_header.items():
            for filepath in paths:
                full_hash = get_file_full_hash(filepath)
                if full_hash:
                    # include size in key to be strictly safe
                    final_key = f"{key}_{full_hash}"
                    full_dict[final_key].append(filepath)
                processed += 1
                if progress_callback and processed % 10 == 0:
                    progress_callback(2, 4, f"计算全量哈希进度: {processed}/{total_files}...")
                    
        duplicates = [paths for paths in full_dict.values() if len(paths) > 1]
        
        if progress_callback:
            progress_callback(3, 4, f"扫描完成，共找到 {len(duplicates)} 组重复文件。正在进行排序与标记...")
            
        # Sort each group: first is the one to keep, rest are to delete
        sorted_duplicates = []
        for group in duplicates:
            # Sort by our scoring function
            sorted_group = sorted(group, key=score_file_for_keeping)
            sorted_duplicates.append(sorted_group)
            
        if progress_callback:
            progress_callback(4, 4, "完成！")
            
        return sorted_duplicates

if __name__ == "__main__":
    # Simple test
    scanner = DuplicateScanner(".")
    dups = scanner.scan(lambda step, total, msg: print(f"[{step}/{total}] {msg}"))
    for i, group in enumerate(dups):
        print(f"Group {i+1}:")
        print(f"  Keep: {group[0]}")
        for dup in group[1:]:
            print(f"  Delete: {dup}")
