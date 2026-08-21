# Contributing

`tavo-skill/` 是稳定版，`tavo-1-0-beta-skill/` 是 Beta 社区结果版，`tavo-1-2-1-skill/` 是 1.2.1 社区事实版；不要在版本之间静默复制结论。稳定版按其 `SKILL.md` 管理证据，两个社区版只接受可公开的事实、适用版本、限制和置信边界。

- 官方能力应对应当前官方文档或当前 MCP runtime docs。
- 实际可用性结论应附可复现的 Android/MCP 证据。
- 不要把旧 Skill、旧缓存或历史 API 当作当前事实。
- 不要提交 API key、Bearer token、Cookie、账号信息或未脱敏请求。
- 不要提交任何 Skill 的 `artifacts/`、设备序列号、IMEI、私有聊天 ID/标题、局域网 MCP 地址或用户绝对路径。
- Beta 和 1.2.1 社区事实版不接收原始取证材料、信息源快照、抓取清单、MCP surface/schema 快照或用于说明结论发现过程的内部记录。
- `archive/` 只保存已经公开的历史快照，不接受新功能修改。

提交前运行：

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py tavo-skill
python3 tavo-skill/scripts/audit_skill_skeleton.py tavo-skill
python3 tavo-skill/scripts/audit_tavo_skill.py tavo-skill
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py tavo-1-0-beta-skill
python3 tavo-1-0-beta-skill/scripts/audit_skill_skeleton.py tavo-1-0-beta-skill
python3 tavo-1-0-beta-skill/scripts/audit_tavo_skill.py tavo-1-0-beta-skill
python3 -B -W error::ResourceWarning -m unittest discover -s tavo-1-0-beta-skill/scripts -p 'test_*.py'
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py tavo-1-2-1-skill
python3 tavo-1-2-1-skill/scripts/audit_skill_skeleton.py tavo-1-2-1-skill
python3 tavo-1-2-1-skill/scripts/audit_tavo_skill.py tavo-1-2-1-skill
python3 -B -W error::ResourceWarning -m unittest discover -s tavo-1-2-1-skill/scripts -p 'test_*.py'
```
