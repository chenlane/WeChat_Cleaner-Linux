import os
import sys
import stat
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QTableWidget, QTableWidgetItem, QProgressBar,
                             QFileDialog, QMessageBox, QHeaderView, QAbstractItemView,
                             QMenu)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QColor, QFont, QDesktopServices

from send2trash import send2trash
from core import DuplicateScanner

class ScanThread(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(list)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        scanner = DuplicateScanner(self.path)
        
        def progress_callback(step, total, msg):
            self.progress.emit(step, total, msg)
            
        duplicates = scanner.scan(progress_callback)
        self.finished.emit(duplicates)

class WxCleanerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WeChat File Cleaner (Linux) - 极速清理工具")
        self.resize(1000, 700)
        
        # Qt natively handles FreeType and FontConfig on Linux, providing perfect anti-aliasing
        font = QFont("Sans Serif", 11)
        self.setFont(font)
        
        self.duplicates = []
        self.to_delete = []
        
        self.setup_ui()
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Top Frame
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("微信文件路径:"))
        
        self.path_entry = QLineEdit()
        self.path_entry.setPlaceholderText("请选择或输入包含重复文件的目录...")
        top_layout.addWidget(self.path_entry)
        
        btn_browse = QPushButton("浏览")
        btn_browse.clicked.connect(self.browse_path)
        top_layout.addWidget(btn_browse)
        
        self.btn_scan = QPushButton("开始扫描")
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_scan.setMinimumWidth(100)
        self.btn_scan.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px;
            }
            QPushButton:hover { background-color: #1E88E5; }
        """)
        top_layout.addWidget(self.btn_scan)
        
        layout.addLayout(top_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["分组", "文件名", "路径", "大小", "状态"])
        
        # Header styling
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.on_table_double_click)
        self.table.setAlternatingRowColors(False) 
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: 1px solid #ccc;
            }
            QTableWidget::item {
                padding: 4px;
                border-bottom: 1px solid #eee;
            }
        """)
        
        # Enable context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.table)
        
        # Progress Frame
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("就绪 (双击列表中的文件可直接预览)")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        # Bottom Frame
        bottom_layout = QHBoxLayout()
        
        btn_clear = QPushButton("清空结果")
        btn_clear.clicked.connect(self.clear_results)
        btn_clear.setStyleSheet("padding: 6px 15px;")
        bottom_layout.addWidget(btn_clear)
        
        bottom_layout.addStretch()
        
        btn_delete = QPushButton("移至回收站")
        btn_delete.clicked.connect(self.delete_selected)
        btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 20px;
            }
            QPushButton:hover { background-color: #E53935; }
        """)
        bottom_layout.addWidget(btn_delete)
        
        layout.addLayout(bottom_layout)
        
    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择微信存储路径")
        if path:
            self.path_entry.setText(path)
            
    def start_scan(self):
        path = self.path_entry.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "错误", "请选择有效的路径！")
            return
            
        self.clear_results()
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("扫描中...")
        
        self.thread = ScanThread(path)
        self.thread.progress.connect(self.update_progress)
        self.thread.finished.connect(self.show_results)
        self.thread.start()
        
    def update_progress(self, step, total, msg):
        if total > 0:
            self.progress_bar.setValue(int((step / total) * 100))
        self.status_label.setText(msg)
        
    def show_results(self, duplicates):
        self.duplicates = duplicates
        self.to_delete = []
        
        total_rows = sum(len(group) for group in duplicates)
        self.table.setRowCount(total_rows)
        
        row = 0
        for i, group in enumerate(duplicates):
            keep_file = group[0]
            delete_files = group[1:]
            
            size_str = self.format_size(os.path.getsize(keep_file))
            
            # Insert keep file
            self.insert_row(row, f"组{i+1}", keep_file, size_str, "保留", is_keep=True)
            row += 1
            
            # Insert delete files
            for df in delete_files:
                self.insert_row(row, f"组{i+1}", df, size_str, "删除", is_keep=False)
                self.to_delete.append(df)
                row += 1
                
        self.status_label.setText(f"扫描完成！找到 {len(self.to_delete)} 个重复文件可清理。(双击列表中的文件可直接预览)")
        self.progress_bar.setValue(100)
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("开始扫描")
        
    def insert_row(self, row, group_name, filepath, size_str, status_text, is_keep):
        filename = os.path.basename(filepath)
        
        item_group = QTableWidgetItem(group_name)
        item_name = QTableWidgetItem(filename)
        item_path = QTableWidgetItem(filepath)
        item_size = QTableWidgetItem(size_str)
        item_status = QTableWidgetItem(status_text)
        
        # High contrast, clean soft color scheme
        if is_keep:
            bg_color = QColor("#F1F8E9") # Very soft green background
            text_color = QColor("#2E7D32") # Dark green text
        else:
            bg_color = QColor("#FFEBEE") # Very soft red background
            text_color = QColor("#C62828") # Dark red text
            
        for item in [item_group, item_name, item_path, item_size, item_status]:
            item.setBackground(bg_color)
            item.setForeground(text_color)
            
            # center align group, size and status
            if item in [item_group, item_size, item_status]:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                
        self.table.setItem(row, 0, item_group)
        self.table.setItem(row, 1, item_name)
        self.table.setItem(row, 2, item_path)
        self.table.setItem(row, 3, item_size)
        self.table.setItem(row, 4, item_status)

    def format_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
        
    def clear_results(self):
        self.table.setRowCount(0)
        self.duplicates = []
        self.to_delete = []
        self.status_label.setText("就绪 (双击列表中的文件可直接预览)")
        self.progress_bar.setValue(0)
        
    def delete_selected(self):
        if not self.to_delete:
            QMessageBox.warning(self, "警告", "没有可清理的文件！")
            return
            
        reply = QMessageBox.question(self, "确认清理", 
                                   f"确定要将 {len(self.to_delete)} 个文件移至回收站吗？\n(此操作安全，可在系统回收站中恢复)",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                   
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            failed = []
            for filepath in list(self.to_delete):
                try:
                    self.move_to_trash(filepath)
                    deleted_count += 1
                except Exception as e:
                    failed.append((filepath, str(e)))
                    
            if failed:
                self.to_delete = [p for p, _ in failed if os.path.exists(p)]
                sample = "\n".join([f"{p}\n  {msg}" for p, msg in failed[:8]])
                QMessageBox.warning(
                    self,
                    "部分失败",
                    f"成功清理 {deleted_count} 个文件。\n失败 {len(failed)} 个文件（常见原因：只读权限）。\n\n示例：\n{sample}",
                )
                self.status_label.setText(f"当前有 {len(self.to_delete)} 个重复文件可清理。(可右键更改状态)")
            else:
                QMessageBox.information(self, "清理完成", f"成功清理 {deleted_count} 个文件！已移至系统回收站。")
                self.clear_results()

    def move_to_trash(self, filepath):
        try:
            send2trash(filepath)
            return
        except PermissionError:
            current_mode = os.stat(filepath).st_mode
            os.chmod(filepath, current_mode | stat.S_IWUSR)
            send2trash(filepath)

    def on_table_double_click(self, item):
        # In PyQt6, doubleClicked signal emits a QModelIndex.
        # However, itemDoubleClicked emits a QTableWidgetItem.
        # Since we connected to doubleClicked, we should use the currently selected row.
        # Actually, let's just get the row from the selected index.
        current_row = self.table.currentRow()
        if current_row >= 0:
            path_item = self.table.item(current_row, 2) # Path is in column 2
            if path_item:
                filepath = path_item.text()
                self.open_file(filepath)
                
    def show_context_menu(self, pos):
        current_row = self.table.currentRow()
        if current_row < 0:
            return
            
        path_item = self.table.item(current_row, 2)
        status_item = self.table.item(current_row, 4)
        
        if not path_item or not status_item:
            return
            
        filepath = path_item.text()
        current_status = status_item.text()
        
        menu = QMenu(self)
        
        action_open = menu.addAction("打开文件")
        action_open_dir = menu.addAction("打开所在文件夹")
        menu.addSeparator()
        
        if current_status == "删除":
            action_toggle = menu.addAction("设为保留 (从清理列表中移除)")
        else:
            action_toggle = menu.addAction("设为删除 (加入清理列表)")
            
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        
        if action == action_open:
            self.open_file(filepath)
        elif action == action_open_dir:
            self.open_directory(filepath)
        elif action == action_toggle:
            self.toggle_item_status(current_row, filepath, current_status)
            
    def toggle_item_status(self, row, filepath, current_status):
        if current_status == "删除":
            # Change to keep
            if filepath in self.to_delete:
                self.to_delete.remove(filepath)
            new_status = "保留"
            bg_color = QColor("#F1F8E9")
            text_color = QColor("#2E7D32")
        else:
            # Change to delete
            if filepath not in self.to_delete:
                self.to_delete.append(filepath)
            new_status = "删除"
            bg_color = QColor("#FFEBEE")
            text_color = QColor("#C62828")
            
        # Update row appearance
        for col in range(5):
            item = self.table.item(row, col)
            if item:
                item.setBackground(bg_color)
                item.setForeground(text_color)
                if col == 4:
                    item.setText(new_status)
                    
        self.status_label.setText(f"当前有 {len(self.to_delete)} 个重复文件可清理。(右键可更改保留/删除状态)")
            
    def open_directory(self, filepath):
        dirpath = os.path.dirname(filepath)
        if not os.path.exists(dirpath):
            QMessageBox.warning(self, "错误", "文件夹不存在！")
            return
            
        try:
            success = QDesktopServices.openUrl(QUrl.fromLocalFile(dirpath))
            if not success:
                if sys.platform.startswith('linux'):
                    subprocess.Popen(['xdg-open', dirpath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif sys.platform == 'win32':
                    os.startfile(dirpath)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', dirpath])
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开文件夹:\n{str(e)}")

    def open_file(self, filepath):
        if not os.path.exists(filepath):
            QMessageBox.warning(self, "错误", "文件不存在，可能已被删除或移动。")
            return
            
        try:
            # Using QDesktopServices is more reliable cross-platform and handles PDF/Office better
            success = QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))
            if not success:
                # Fallback to subprocess if Qt fails
                if sys.platform.startswith('linux'):
                    subprocess.Popen(['xdg-open', filepath], 
                                  stdout=subprocess.DEVNULL, 
                                  stderr=subprocess.DEVNULL)
                elif sys.platform == 'win32':
                    os.startfile(filepath)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', filepath])
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开文件:\n{str(e)}")

def run_app():
    # Set high DPI scaling attributes before app creation
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        
    app = QApplication(sys.argv)
    
    # Use standard modern Fusion style
    app.setStyle("Fusion")
    
    window = WxCleanerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_app()
