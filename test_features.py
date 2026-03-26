import os
import shutil
import tempfile
import zipfile

from core import DuplicateScanner, ScanOptions, effective_savings

try:
    from PIL import Image
except Exception:
    Image = None


def make_file(path: str, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def make_fake_pdf(path: str, creation: str):
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"2 0 obj\n<< /CreationDate ("
        + creation.encode("ascii")
        + b") /Producer (X) >>\nendobj\n"
        b"trailer\n<<>>\n%%EOF\n"
    )
    make_file(path, body)


def make_fake_docx(path: str, core: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", "<w:document><w:body><w:p>hello</w:p></w:body></w:document>")
        zf.writestr("docProps/core.xml", f"<cp:coreProperties><dc:creator>{core}</dc:creator></cp:coreProperties>")


def test_head_tail_sampling():
    d = tempfile.mkdtemp(prefix="wxcleaner_test_")
    try:
        a = os.path.join(d, "a.bin")
        b = os.path.join(d, "b.bin")
        head = b"A" * 4096
        make_file(a, head + b"X" * 4096)
        make_file(b, head + b"Y" * 4096)
        opts = ScanOptions(sample_mode="head_tail", parallel=False)
        res = DuplicateScanner(d, options=opts).scan()
        assert len([g for g in res.groups if g.kind == "exact"]) == 0
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_exact_duplicates_and_hardlink_savings():
    d = tempfile.mkdtemp(prefix="wxcleaner_test_")
    try:
        a = os.path.join(d, "a.txt")
        b = os.path.join(d, "b(1).txt")
        make_file(a, b"hello world\n" * 100)
        shutil.copy(a, b)

        c = os.path.join(d, "c.txt")
        dlink = os.path.join(d, "c(1).txt")
        make_file(c, b"hardlink content\n" * 100)
        os.link(c, dlink)

        res = DuplicateScanner(d, options=ScanOptions(parallel=False)).scan()
        exact = [g for g in res.groups if g.kind == "exact"]
        assert len(exact) >= 2

        delete_list = res.default_delete_list()
        freed = effective_savings(res.file_info, delete_list)
        assert freed > 0

        link_inode = (res.file_info[c].dev, res.file_info[c].ino)
        link_deletes = [p for p in delete_list if (res.file_info[p].dev, res.file_info[p].ino) == link_inode]
        assert len(link_deletes) == 1
        assert effective_savings(res.file_info, link_deletes) == 0
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_near_pdf_normalization():
    d = tempfile.mkdtemp(prefix="wxcleaner_test_")
    try:
        p1 = os.path.join(d, "a.pdf")
        p2 = os.path.join(d, "a(1).pdf")
        make_fake_pdf(p1, "D:20260101010101")
        make_fake_pdf(p2, "D:20260202020202")

        res0 = DuplicateScanner(d, options=ScanOptions(parallel=False)).scan()
        assert len(res0.groups) == 0

        res = DuplicateScanner(d, options=ScanOptions(parallel=False, enable_pdf_normalize=True)).scan()
        near = [g for g in res.groups if g.kind == "near_pdf"]
        assert len(near) == 1
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_near_office_normalization():
    d = tempfile.mkdtemp(prefix="wxcleaner_test_")
    try:
        f1 = os.path.join(d, "a.docx")
        f2 = os.path.join(d, "a(1).docx")
        make_fake_docx(f1, "Alice")
        make_fake_docx(f2, "Bob")
        res = DuplicateScanner(d, options=ScanOptions(parallel=False, enable_office_normalize=True)).scan()
        near = [g for g in res.groups if g.kind == "near_office"]
        assert len(near) == 1
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_near_image_perceptual():
    if Image is None:
        return
    d = tempfile.mkdtemp(prefix="wxcleaner_test_")
    try:
        img1 = os.path.join(d, "a.png")
        img2 = os.path.join(d, "a.jpg")
        im = Image.new("RGB", (64, 64), (120, 30, 200))
        im.save(img1, format="PNG")
        im.save(img2, format="JPEG", quality=85)
        res = DuplicateScanner(d, options=ScanOptions(parallel=False, enable_image_perceptual=True)).scan()
        near = [g for g in res.groups if g.kind == "near_image"]
        assert len(near) == 1
    finally:
        shutil.rmtree(d, ignore_errors=True)

def test_near_archive_normalization():
    d = tempfile.mkdtemp(prefix="wxcleaner_test_")
    try:
        z1 = os.path.join(d, "a.zip")
        z2 = os.path.join(d, "a(1).zip")
        with zipfile.ZipFile(z1, "w") as zf:
            zf.writestr("x.txt", "hello")
            zf.writestr("y.txt", "world")
        with zipfile.ZipFile(z2, "w") as zf:
            zf.writestr("y.txt", "world")
            zf.writestr("x.txt", "hello")
        res = DuplicateScanner(d, options=ScanOptions(parallel=False, enable_archive_normalize=True)).scan()
        near = [g for g in res.groups if g.kind == "near_archive"]
        assert len(near) == 1
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    test_head_tail_sampling()
    test_exact_duplicates_and_hardlink_savings()
    test_near_pdf_normalization()
    test_near_office_normalization()
    test_near_archive_normalization()
    test_near_image_perceptual()
