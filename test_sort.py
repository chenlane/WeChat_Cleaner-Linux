import os
import re

files = [
    "/home/scholl_chen/Documents/xwechat_files/scholl_chen_b773/msg/file/2026-01/提纲(3).pptx",
    "/home/scholl_chen/Documents/xwechat_files/scholl_chen_b773/msg/file/2026-01/提纲(1).pptx",
    "/home/scholl_chen/Documents/xwechat_files/scholl_chen_b773/msg/file/2026-01/提纲.pptx",
    "/home/scholl_chen/Documents/xwechat_files/scholl_chen_b773/msg/file/2026-01/提纲(2).pptx"
]

def score(filepath):
    filename = os.path.basename(filepath)
    has_suffix = 1 if re.search(r'\(\d+\)', filename) else 0
    mtime = os.path.getmtime(filepath)
    return (has_suffix, mtime, len(filepath))

sorted_files = sorted(files, key=score)
for f in sorted_files:
    print(f, score(f))
