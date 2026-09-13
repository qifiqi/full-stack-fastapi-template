补齐 `.agents/skills/` 下缺失的 fastapi、sqlmodel 两个 skill（按 library-skills 官方修复流程，同时修复 `.claude/skills/` 镜像）：

1. **安装依赖**：在仓库根目录运行 `uv sync`（根 pyproject 是 uv workspace，包含 backend），生成 `.venv` 并安装 fastapi、sqlmodel 包（其包内捆绑 `.agents/skills/`）。
2. **检查状态**：运行 `uvx library-skills --check`（含 `--claude`）确认断链情况，不改文件。
3. **修复**：运行 `uvx library-skills --yes --claude` 重建/修复 fastapi、sqlmodel 的托管链接。
4. **Windows 兜底**：若工具因 Windows 符号链接权限失败，改用目录 junction（`cmd //c mklink //J`，无需管理员权限）指向 `.venv/Lib/site-packages/{fastapi,sqlmodel}/.agents/skills/...` 的实际路径，`.agents/skills` 与 `.claude/skills` 两处同样处理。
5. **验收**：能成功读取 `.agents/skills/fastapi/SKILL.md` 与 `.agents/skills/sqlmodel/SKILL.md`；`uvx library-skills list` 显示 3 个 skill 均已安装。另外运行 `uvx library-skills scan --json` 检查是否有其他已安装包捆绑了新 skill，如有仅在总结中报告、不擅自安装。

说明：`library-skills` 本身完好，无需处理；不手工删除或改写任何 skill 目录。