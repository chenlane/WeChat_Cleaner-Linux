import os
import shutil

def create_test_files():
    base_dir = "test_wechat_data"
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
        
    os.makedirs(base_dir)
    
    # Create original files
    with open(os.path.join(base_dir, "document.pdf"), "w") as f:
        f.write("Hello, World! This is a test document." * 100)
        
    with open(os.path.join(base_dir, "image.png"), "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"0" * 1000)
        
    # Create duplicate files with (1), (2) pattern
    shutil.copy(os.path.join(base_dir, "document.pdf"), os.path.join(base_dir, "document(1).pdf"))
    shutil.copy(os.path.join(base_dir, "document.pdf"), os.path.join(base_dir, "document(2).pdf"))
    shutil.copy(os.path.join(base_dir, "image.png"), os.path.join(base_dir, "image(1).png"))
    
    # Create another file with different content but same size? (Hard, let's just create different file)
    with open(os.path.join(base_dir, "unique.txt"), "w") as f:
        f.write("I am unique")
        
    print("Test files created.")

if __name__ == "__main__":
    create_test_files()
