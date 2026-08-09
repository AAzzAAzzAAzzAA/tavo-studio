# Tavo Skills

面向 Tavo 的百科式 Codex Skills，覆盖软件能力问答与创作工作流。仓库同时保留稳定版、Tavo 1.0 Beta 社区结果版和旧项目归档。

## 仓库结构

```text
archive/                旧 Tavo Studio 与 Dev Kit 的只读历史归档
tavo-skill/             当前稳定版 Skill
tavo-1-0-beta-skill/    Tavo 1.0 内测版完整 Skill
```

## 包含内容

- Tavo 能力边界与非常规需求判断。
- 角色卡、人格、开场白和对话示例。
- 世界书、预设、正则、宏、EJS 与长记忆。
- Advanced Rendering、TavoJS 与 `.tpg` 插件。
- 图片、语音、设置、数据和 MCP 工作流。
- 稳定版中的验证资料，以及 Beta 社区版中的自包含离线校验工具。

## 安装稳定版

```bash
mkdir -p ~/.codex/skills
cp -R tavo-skill ~/.codex/skills/tavo-skill
```

之后在 Codex 中使用 `$tavo-skill`，或直接提出 Tavo 能力、创作、调试与验证需求。

## 安装 1.0 Beta

```bash
mkdir -p ~/.codex/skills
cp -R tavo-1-0-beta-skill ~/.codex/skills/tavo-skill
```

Beta 使用 `$tavo-skill`。它与稳定版具有相同的 Skill 名称和触发名，因此不要把两者同时安装到同一个 Agent；请选择其中一个安装。仓库中的版本目录用于区分发布渠道，安装目标仍须命名为 `tavo-skill`。

Beta 是自包含、结果导向的社区包：保留创作、Prompt Lab、EJS、正则、插件校验和受限 MCP 客户端等可用能力，但不分发原始设备记录、请求捕获、信息源快照或取证过程。

## 证据原则

稳定版将“声明面”和“运行可靠性”分开判断：

1. 当前官方文档用于确认产品公开声明。
2. 当前 MCP schema 与 runtime docs 用于确认机器可见接口。
3. Android 真机实验用于确认实际效果、渲染、持久化和回归。
4. 历史材料只作为待验证素材，不覆盖当前证据。

Beta 只交付整理后的能力状态、适用版本、限制和置信边界；未建立的能力会明确标为 `not-established`，不会随包公开其发现过程。

稳定版详见 [`tavo-skill/SKILL.md`](tavo-skill/SKILL.md)，内测版详见 [`tavo-1-0-beta-skill/SKILL.md`](tavo-1-0-beta-skill/SKILL.md)。

## 历史版本

旧 `tavo-studio` Skill 和 Dev Kit 位于 [`archive/legacy-2026-07-11/`](archive/legacy-2026-07-11/)，原始快照也保留在 Git 标签：

```text
legacy-tavo-studio-kit-2026-07-11
```

## License

MIT，见 [LICENSE](LICENSE)。
