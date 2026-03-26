# WxCleaner-Linux

一款专为 Linux 环境设计的微信重复文件清理工具。通过“文件大小 → 头部哈希 → 全量哈希”的三级筛选策略，极速且准确地识别重复文件；内置现代化 GUI（PyQt6）与 CLI 双模式，支持可视化预览、安全删除（移至回收站）与权限修复。

## 目录
- 项目简介
- 为什么需要这款工具
- 核心特性
- 技术栈
- 安装与运行
- 使用说明
  - GUI 图形界面
  - CLI 命令行
- 高级能力
- 权限与安全
- 常见问题
- 开发者指南
- 许可证
- 致谢

## 项目简介
微信在文件转发与保存过程中，经常产生大量重复文件，如 `xxx(1).pdf`、`xxx(2).docx` 等，长期累积会占用大量磁盘空间。本工具面向 Linux 用户，提供强大的重复识别与一键清理能力，同时保障内容安全与预览体验。

## 为什么需要这款工具
- 微信的重复文件命名策略会导致同一文件出现多份副本
- 跨月份目录中存在大量“内容完全一致”的拷贝
- 手工比对效率低、易误删

## 核心特性
- 极速识别：三级去重策略，确保 100% 内容一致才判定为重复
  - 基于大小分组 → 头部哈希（默认 4KB）→ 全量哈希（MD5）
  - 参考实现见 [core.py](file:///home/scholl_chen/claude_project_deepseek/wx_cleaner/core.py)
- 智能保留：自动优先保留“无后缀且最近修改”的版本（避免误删你刚编辑过的原件）
- 安全删除：使用系统回收站（send2trash），支持“只读文件”权限自动修复后再删除
  - GUI 实现见 [gui.py:move_to_trash](file:///home/scholl_chen/claude_project_deepseek/wx_cleaner/gui.py#L290-L297)
  - CLI 实现见 [cli.py:move_to_trash](file:///home/scholl_chen/claude_project_deepseek/wx_cleaner/cli.py#L7-L20)
- 现代化 GUI：采用 PyQt6 与 Fusion 风格，字体抗锯齿，颜色对比度舒适
  - 支持双击预览（系统默认应用）与右键菜单（打开文件、打开所在文件夹、切换保留/删除）
  - 代码位置 [gui.py](file:///home/scholl_chen/claude_project_deepseek/wx_cleaner/gui.py)
- CLI 支持：无需图形环境即可批量扫描与清理
  - 代码位置 [cli.py](file:///home/scholl_chen/claude_project_deepseek/wx_cleaner/cli.py)

## 技术栈
- 语言：Python 3.8+
- GUI：PyQt6（Fusion 风格，完美抗锯齿）
- 核心库：
  - send2trash（跨平台移至回收站）
  - Pillow（图像库，后续预览扩展可用）
  - tqdm（命令行进度，可按需使用）

依赖文件：[requirements.txt](file:///home/scholl_chen/claude_project_deepseek/wx_cleaner/requirements.txt)

## 安装与运行
```bash
# 1) 安装依赖
pip install -r requirements.txt

# 2) 运行 GUI
python3 main.py

# 3) 运行 CLI（示例）
python3 main.py --cli /path/to/wechat/dir --dry-run
python3 main.py --cli /path/to/wechat/dir -y
```

主入口：[main.py](file:///home/scholl_chen/claude_project_deepseek/wx_cleaner/main.py)

## 使用说明

### GUI 图形界面
- 打开程序后，点击“浏览”选择微信文件存储目录（示例：`~/Documents/xwechat_files/.../msg/file/`）
- 点击“开始扫描”，等待进度完成
- 在列表中：
  - 绿色为“保留”，红色为“删除”
  - 双击任意条目即可用系统默认应用预览文件
  - 右键菜单可执行“打开文件”、“打开所在文件夹”、“设为保留/删除”
- 点击“移至回收站”，执行安全删除（支持只读文件自动修复权限）

### CLI 命令行
```bash
# 仅预览将要删除的文件（不做删除）
python3 main.py --cli /path/to/wechat/dir --dry-run

# 正式执行，删除前交互确认
python3 main.py --cli /path/to/wechat/dir

# 静默执行，直接进入回收站
python3 main.py --cli /path/to/wechat/dir -y
```

## 高级能力
- 重复判定严格：只有当“全量哈希一致”时，才会被判定为重复并建议清理
- 保留排序策略（参考 [core.py](file:///home/scholl_chen/claude_project_deepseek/wx_cleaner/core.py)）：
  1. 文件名是否带 `(1)`, `(2)` 等后缀（优先保留不带后缀）
  2. 修改时间（优先保留最近修改）
  3. 文件名长度（较短的优先）

## 权限与安全
- 删除操作仅“移至系统回收站”，可在回收站恢复
- 针对只读文件：自动执行 `chmod u+w` 后再移入回收站
- 若仍失败（例如不可变属性 `chattr +i` 或跨权限用户），GUI 会弹窗展示失败数量与示例路径

## 常见问题
- 双击无法预览 PDF？
  - 已采用 `QDesktopServices.openUrl` 优先打开，若桌面关联缺失会自动退回 `xdg-open`。请确保系统已安装并配置默认 PDF 阅读器（如 Evince/Okular）。
- 扫描后显示有重复，但“移至回收站”成功为 0？
  - 常见原因是文件只读。GUI/CLI 已内置自动修复写权限再删除，如果仍失败，请检查文件是否为不可变属性或属主不匹配。

## 开发者指南
- 核心算法：[core.py](file:///home/scholl_chen/claude_project_deepseek/wx_cleaner/core.py)
- GUI 入口与交互：[gui.py](file:///home/scholl_chen/claude_project_deepseek/wx_cleaner/gui.py)
- CLI 入口：[cli.py](file:///home/scholl_chen/claude_project_deepseek/wx_cleaner/cli.py)
- 程序主入口：[main.py](file:///home/scholl_chen/claude_project_deepseek/wx_cleaner/main.py)

建议使用 Python 3.10+ 与现代 Linux 桌面环境进行开发与调试。

## 许可证
本项目采用 MIT 许可证。

## 致谢
- 灵感与算法策略参考项目：  
  GitHub - [WxCleaner](https://github.com/yqxie1991/WxCleaner)  
  感谢原作者对“文件大小 → 头部哈希 → 全量哈希”三级筛选策略以及安全删除理念的贡献。

