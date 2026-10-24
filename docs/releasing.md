# 每版同步 GitHub

每次 moqi 版本升级，按以下顺序处理。首次同步前先确定 GitHub 仓库地址及可见性，并审查将要公开的完整提交历史。

1. 同步更新 `pyproject.toml` 和 `moqi/__init__.py` 的版本号，在 `CHANGELOG.md` 记录变化。
2. 运行 `python -m pytest -q`、`python tests/mcp_smoke.py` 和 `git diff --check`。联网功能要分别验证无密钥路径及配置密钥后的实际查询；没有密钥时如实标注未实测。
3. 检查 `git status`、`git ls-files` 与待推送的完整历史，确认没有密钥、私人默契记录、测试临时数据或其他个人信息。
4. 提交该版本，创建对应标签，例如 `v0.2.0b4`；将提交和标签推送至项目的 GitHub 仓库。核对远端提交 SHA 与标签。
5. 查看 GitHub Actions 的 Windows/Linux 检查结果。通过后再把版本描述为可供对应平台安装；若失败则修复并发布新的修订版本。

首次建仓和设定远端只需做一次。未配置远端时，本地提交和标签不等于已同步到 GitHub；不能对外声称已发布。
