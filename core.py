<<<<<<< HEAD
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
=======
import hashlib
import os
import re
import threading
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple
import tarfile

try:
    from PIL import Image
except Exception:
    Image = None


@dataclass(frozen=True)
class FileInfo:
    path: str
    size: int
    mtime: float
    dev: int
    ino: int
    nlink: int


@dataclass(frozen=True)
class ScanOptions:
    sample_size: int = 4096
    tail_size: int = 4096
    sample_mode: str = "head_tail"
    full_hash_chunk_size: int = 1024 * 256
    parallel: bool = True
    max_workers: Optional[int] = None
    io_concurrency: int = 4
    enable_image_perceptual: bool = False
    enable_pdf_normalize: bool = False
    enable_office_normalize: bool = False
    enable_archive_normalize: bool = False


@dataclass
class DuplicateGroup:
    group_id: int
    kind: str
    keep_path: str
    paths: List[str]

    def deletable_paths(self) -> List[str]:
        if self.kind != "exact":
            return []
        return [p for p in self.paths if p != self.keep_path]


@dataclass
class ScanResult:
    groups: List[DuplicateGroup]
    file_info: Dict[str, FileInfo]

    def default_delete_list(self) -> List[str]:
        result: List[str] = []
        for g in self.groups:
            result.extend(g.deletable_paths())
        return result


def _safe_stat(path: str) -> Optional[os.stat_result]:
    try:
        return os.stat(path, follow_symlinks=False)
    except OSError:
        return None


def collect_file_info(directory: str) -> Dict[str, FileInfo]:
    info: Dict[str, FileInfo] = {}
    for root, _, files in os.walk(directory):
        for name in files:
            path = os.path.join(root, name)
            st = _safe_stat(path)
            if not st:
                continue
            if st.st_size <= 0:
                continue
            info[path] = FileInfo(
                path=path,
                size=int(st.st_size),
                mtime=float(st.st_mtime),
                dev=int(st.st_dev),
                ino=int(st.st_ino),
                nlink=int(st.st_nlink),
            )
    return info


def score_file_for_keeping(file_info: FileInfo) -> Tuple[int, float, int]:
    filename = os.path.basename(file_info.path)
    has_suffix = 1 if re.search(r"\(\d+\)", filename) else 0
    return (has_suffix, -file_info.mtime, len(filename))


def _md5_bytes(data: bytes) -> str:
    h = hashlib.md5()
    h.update(data)
    return h.hexdigest()


def sample_hash(path: str, size: int, sample_size: int, tail_size: int, mode: str, io_sem: threading.Semaphore) -> Optional[str]:
    try:
        with io_sem:
            with open(path, "rb") as f:
                if mode == "head":
                    return _md5_bytes(f.read(sample_size))
                head = f.read(sample_size)
                if size <= sample_size + tail_size:
                    rest = f.read()
                    return _md5_bytes(head + rest)
                f.seek(max(0, size - tail_size))
                tail = f.read(tail_size)
                return _md5_bytes(head + tail)
    except OSError:
        return None


def full_hash(path: str, chunk_size: int, io_sem: threading.Semaphore) -> Optional[str]:
    try:
        h = hashlib.md5()
        with io_sem:
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def effective_savings(file_info: Dict[str, FileInfo], delete_paths: Iterable[str]) -> int:
    by_inode: Dict[Tuple[int, int], List[str]] = defaultdict(list)
    for p in delete_paths:
        fi = file_info.get(p)
        if not fi:
            continue
        by_inode[(fi.dev, fi.ino)].append(p)

    freed = 0
    for (dev, ino), paths in by_inode.items():
        fi = file_info.get(paths[0])
        if not fi:
            continue
        if len(paths) >= fi.nlink:
            freed += fi.size
    return freed


def _parallel_map(
    paths: List[str],
    func: Callable[[str], Optional[str]],
    max_workers: int,
) -> Dict[str, str]:
    result: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_to_path = {ex.submit(func, p): p for p in paths}
        for fut in as_completed(future_to_path):
            p = future_to_path[fut]
            try:
                v = fut.result()
            except Exception:
                v = None
            if v:
                result[p] = v
    return result


def _is_image(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff", ".tif"}


def image_dhash(path: str) -> Optional[Tuple[str, int, int]]:
    if Image is None:
        return None
    try:
        with Image.open(path) as im0:
            w0, h0 = im0.size
            im = im0.convert("L").resize((9, 8))
            px = list(im.getdata())
            diff = []
            for row in range(8):
                row_start = row * 9
                for col in range(8):
                    a = px[row_start + col]
                    b = px[row_start + col + 1]
                    diff.append(1 if a > b else 0)
            bits = 0
            for i, b in enumerate(diff):
                bits = (bits << 1) | b
            return (f"{bits:016x}", w0, h0)
    except Exception:
        return None


def pdf_normalized_hash(path: str, io_sem: threading.Semaphore) -> Optional[str]:
    try:
        with io_sem:
            with open(path, "rb") as f:
                data = f.read()
        for key in [b"/CreationDate", b"/ModDate", b"/Producer", b"/Creator", b"/Author", b"/Title"]:
            data = re.sub(rb"(" + re.escape(key) + rb"\s*\([^)]*\))", key + b"(X)", data)
            data = re.sub(rb"(" + re.escape(key) + rb"\s*<[^>]*>)", key + b"<X>", data)
        return _md5_bytes(data)
    except Exception:
        return None


def office_normalized_hash(path: str) -> Optional[str]:
    ext = os.path.splitext(path)[1].lower()
    if ext not in {".docx", ".xlsx", ".pptx"}:
        return None
    try:
        parts: List[bytes] = []
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            if ext == ".docx":
                wanted = [n for n in names if n.startswith("word/") and n.endswith(".xml")]
                wanted = [n for n in wanted if not n.startswith("word/_rels/")]
                wanted = [n for n in wanted if n not in {"word/settings.xml"}]
                wanted.sort()
            elif ext == ".xlsx":
                wanted = [n for n in names if n.startswith("xl/") and n.endswith(".xml")]
                wanted = [n for n in wanted if not n.startswith("xl/_rels/")]
                wanted = [n for n in wanted if not n.startswith("xl/printerSettings/")]
                wanted = [n for n in wanted if not n.startswith("xl/metadata/")]
                wanted.sort()
            else:
                wanted = [n for n in names if n.startswith("ppt/") and n.endswith(".xml")]
                wanted = [n for n in wanted if not n.startswith("ppt/_rels/")]
                wanted.sort()
            for n in wanted:
                if n.startswith("docProps/"):
                    continue
                raw = zf.read(n)
                raw = re.sub(rb"\s+", b" ", raw)
                parts.append(raw)
        return _md5_bytes(b"\n".join(parts))
    except Exception:
        return None


def _zip_normalized_hash(path: str) -> Optional[str]:
    try:
        parts: List[bytes] = []
        with zipfile.ZipFile(path, "r") as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            names.sort()
            for n in names:
                try:
                    raw = zf.read(n)
                except Exception:
                    raw = b""
                parts.append(n.encode("utf-8", errors="ignore") + b"\n" + hashlib.md5(raw).digest())
        return _md5_bytes(b"".join(parts))
    except Exception:
        return None


def _tar_normalized_hash(path: str) -> Optional[str]:
    try:
        parts: List[bytes] = []
        with tarfile.open(path, "r:*") as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            members.sort(key=lambda m: m.name)
            for m in members:
                try:
                    f = tf.extractfile(m)
                    raw = f.read() if f else b""
                except Exception:
                    raw = b""
                parts.append(m.name.encode("utf-8", errors="ignore") + b"\n" + hashlib.md5(raw).digest())
        return _md5_bytes(b"".join(parts))
    except Exception:
        return None


def archive_normalized_hash(path: str) -> Optional[str]:
    ext = os.path.splitext(path)[1].lower()
    if zipfile.is_zipfile(path):
        return _zip_normalized_hash(path)
    try:
        if tarfile.is_tarfile(path) or ext in {".tar", ".tgz", ".tar.gz", ".tbz2", ".tar.bz2"}:
            return _tar_normalized_hash(path)
    except Exception:
        pass
    return None


class DuplicateScanner:
    def __init__(self, directory: str, options: Optional[ScanOptions] = None):
        self.directory = directory
        self.options = options or ScanOptions()

    def scan(self, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> ScanResult:
        opts = self.options
        steps_total = 6
        if progress_callback:
            progress_callback(0, steps_total, "正在收集文件信息...")

        info = collect_file_info(self.directory)
        files = list(info.keys())
        size_dict: Dict[int, List[str]] = defaultdict(list)
        for p in files:
            size_dict[info[p].size].append(p)
        candidates_by_size = {s: ps for s, ps in size_dict.items() if len(ps) > 1}

        if progress_callback:
            progress_callback(1, steps_total, f"根据大小找到 {len(candidates_by_size)} 组候选，正在计算采样哈希...")

        io_sem = threading.BoundedSemaphore(max(1, int(opts.io_concurrency)))
        max_workers = opts.max_workers or min(8, (os.cpu_count() or 4))
        max_workers = max(1, int(max_workers))

        sample_dict: Dict[str, List[str]] = defaultdict(list)
        sample_paths = [p for ps in candidates_by_size.values() for p in ps]

        def sample_fn(p: str) -> Optional[str]:
            fi = info.get(p)
            if not fi:
                return None
            return sample_hash(p, fi.size, opts.sample_size, opts.tail_size, opts.sample_mode, io_sem)

        if opts.parallel and sample_paths:
            sample_map = _parallel_map(sample_paths, sample_fn, max_workers=max_workers)
        else:
            sample_map = {p: sample_fn(p) for p in sample_paths if sample_fn(p)}

        for p, sh in sample_map.items():
            fi = info[p]
            key = f"{fi.size}_{sh}"
            sample_dict[key].append(p)

        candidates_by_sample = {k: ps for k, ps in sample_dict.items() if len(ps) > 1}

        if progress_callback:
            progress_callback(2, steps_total, f"根据采样哈希找到 {len(candidates_by_sample)} 组候选，正在计算全量哈希...")

        full_dict: Dict[str, List[str]] = defaultdict(list)
        full_paths = [p for ps in candidates_by_sample.values() for p in ps]

        def full_fn(p: str) -> Optional[str]:
            return full_hash(p, opts.full_hash_chunk_size, io_sem)

        if opts.parallel and full_paths:
            full_map = _parallel_map(full_paths, full_fn, max_workers=max_workers)
        else:
            full_map = {p: full_fn(p) for p in full_paths if full_fn(p)}

        for p, fh in full_map.items():
            fi = info[p]
            key = f"{fi.size}_{fh}"
            full_dict[key].append(p)

        exact_groups_raw = [ps for ps in full_dict.values() if len(ps) > 1]
        exact_groups: List[DuplicateGroup] = []
        group_id = 1
        for ps in exact_groups_raw:
            ps_sorted = sorted(ps, key=lambda p: score_file_for_keeping(info[p]))
            keep = ps_sorted[0]
            exact_groups.append(DuplicateGroup(group_id=group_id, kind="exact", keep_path=keep, paths=ps_sorted))
            group_id += 1

        if progress_callback:
            progress_callback(3, steps_total, f"严格重复识别完成：{len(exact_groups)} 组。")

        near_groups: List[DuplicateGroup] = []
        if opts.enable_image_perceptual or opts.enable_pdf_normalize or opts.enable_office_normalize or opts.enable_archive_normalize:
            if progress_callback:
                progress_callback(4, steps_total, "正在进行可选增强模式识别（默认不参与自动清理）...")

            near_id = 1
            if opts.enable_image_perceptual and Image is not None:
                im_groups: Dict[Tuple[str, int, int], List[str]] = defaultdict(list)
                for p, fi in info.items():
                    if not _is_image(p):
                        continue
                    h = image_dhash(p)
                    if not h:
                        continue
                    im_groups[h].append(p)
                for k, ps in im_groups.items():
                    if len(ps) < 2:
                        continue
                    ps_sorted = sorted(ps, key=lambda p: score_file_for_keeping(info[p]))
                    near_groups.append(DuplicateGroup(group_id=near_id, kind="near_image", keep_path=ps_sorted[0], paths=ps_sorted))
                    near_id += 1

            if opts.enable_pdf_normalize:
                pdf_groups: Dict[str, List[str]] = defaultdict(list)
                pdf_paths = [p for p in info.keys() if os.path.splitext(p)[1].lower() == ".pdf"]

                def pdf_fn(p: str) -> Optional[str]:
                    return pdf_normalized_hash(p, io_sem)

                if opts.parallel and pdf_paths:
                    pdf_map = _parallel_map(pdf_paths, pdf_fn, max_workers=max_workers)
                else:
                    pdf_map = {p: pdf_fn(p) for p in pdf_paths if pdf_fn(p)}
                for p, h in pdf_map.items():
                    pdf_groups[h].append(p)
                for h, ps in pdf_groups.items():
                    if len(ps) < 2:
                        continue
                    ps_sorted = sorted(ps, key=lambda p: score_file_for_keeping(info[p]))
                    near_groups.append(DuplicateGroup(group_id=near_id, kind="near_pdf", keep_path=ps_sorted[0], paths=ps_sorted))
                    near_id += 1

            if opts.enable_office_normalize:
                office_groups: Dict[str, List[str]] = defaultdict(list)
                office_paths = [
                    p
                    for p in info.keys()
                    if os.path.splitext(p)[1].lower() in {".docx", ".xlsx", ".pptx"}
                ]

                def off_fn(p: str) -> Optional[str]:
                    return office_normalized_hash(p)

                if opts.parallel and office_paths:
                    off_map = _parallel_map(office_paths, off_fn, max_workers=max_workers)
                else:
                    off_map = {p: off_fn(p) for p in office_paths if off_fn(p)}
                for p, h in off_map.items():
                    office_groups[h].append(p)
                for h, ps in office_groups.items():
                    if len(ps) < 2:
                        continue
                    ps_sorted = sorted(ps, key=lambda p: score_file_for_keeping(info[p]))
                    near_groups.append(DuplicateGroup(group_id=near_id, kind="near_office", keep_path=ps_sorted[0], paths=ps_sorted))
                    near_id += 1

            if opts.enable_archive_normalize:
                arch_groups: Dict[str, List[str]] = defaultdict(list)
                arch_paths = [
                    p
                    for p in info.keys()
                    if os.path.splitext(p)[1].lower() in {".zip", ".tar", ".tgz", ".gz", ".bz2", ".tar.gz", ".tar.bz2", ".tbz2"}
                    or zipfile.is_zipfile(p)
                    or tarfile.is_tarfile(p)
                ]

                def arch_fn(p: str) -> Optional[str]:
                    return archive_normalized_hash(p)

                if opts.parallel and arch_paths:
                    arch_map = _parallel_map(arch_paths, arch_fn, max_workers=max_workers)
                else:
                    arch_map = {p: arch_fn(p) for p in arch_paths if arch_fn(p)}
                for p, h in arch_map.items():
                    arch_groups[h].append(p)
                for h, ps in arch_groups.items():
                    if len(ps) < 2:
                        continue
                    ps_sorted = sorted(ps, key=lambda p: score_file_for_keeping(info[p]))
                    near_groups.append(DuplicateGroup(group_id=near_id, kind="near_archive", keep_path=ps_sorted[0], paths=ps_sorted))
                    near_id += 1

        groups = exact_groups + near_groups

        if progress_callback:
            progress_callback(5, steps_total, "完成！")

        return ScanResult(groups=groups, file_info=info)
>>>>>>> b1a2bad (feat: PyQt6 双视图（严格/近似）、Ctrl/Shift 多选、首尾采样并行哈希、硬链接识别、压缩包/PDF/Office近似模式、失败分类、README 更新)
