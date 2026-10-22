# 贡献指南

感谢你对照片管理系统的关注！本项目采用 **GPLv3 + 商业双重授权**模式，提交贡献前请阅读本文。

## 行为准则

- 尊重每一位贡献者，讨论对事不对人
- 本项目红线：**程序内无删除原图功能**（详见 docs/DEVELOPMENT.md）

## 如何贡献

1. **提 Issue**：Bug 报告请附复现步骤、环境（Windows/麒麟、版本号）；功能建议请说明使用场景
2. **提 Pull Request**：
   - Fork 本仓库，从 `main` 切出功能分支
   - 一个 PR 只做一件事，附清晰的变更说明
   - 提交前确保通过：
     ```powershell
     python -m unittest discover -s tests -p "test_*.py"
     $env:QT_QPA_PLATFORM="offscreen"; python tests/smoke_ui.py
     python tools/gui_check.py --offscreen
     ```
   - 版本号递增约定：`photo_manager/__init__.py` 的 `APP_VERSION`（小步提交）
3. **代码风格**：遵循现有代码约定（见 docs/DEVELOPMENT.md「开发约定」一节）

## 版权与双重授权（重要）

本项目由版权持有人以 **GPLv3 或（商业客户选择的）商业授权** 双轨发布。为使双重授权模式成立，**版权持有人必须持有全部代码的完整版权**。因此：

- **提交贡献即表示你同意签署本项目的贡献者许可协议（CLA）**，将贡献的版权转让给项目持有人（见 [CLA.md](CLA.md)）
- 首次提交 PR 时，维护者会引导你完成 CLA 签署（电子签署即可）
- 未签署 CLA 的贡献无法合入 `main`

如果你不愿转让版权，仍欢迎以 Issue 形式反馈问题与建议。

## 商业授权咨询

企业嵌入、闭源集成、OEM 预装等场景需要商业授权，详见 [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)。
