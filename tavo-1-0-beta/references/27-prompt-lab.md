# Tavo Prompt Lab v2

Prompt Lab 是本 Skill 内置的纯文本测试入口。它把 Tavo native 预设、角色卡、Persona、世界书、聊天历史和本轮输入编译成 OpenAI-compatible Chat Completions 请求；`compile` 只展示最终请求，`run` 再把同一请求发给指定模型并返回模型反应。

它用于快速回答“这些文字在 Tavo 的拼装顺序下会让模型怎么回应”。v2 会在本地隔离进程中先渲染作者资产里的 prompt-field EJS，再运行宏和提示词拼装；仍不连接真机、不读取 Tavo 数据库，也不处理高级前端、TavoJS、TPG、图片、语音或正则显示管线。

## Agent 入口

唯一公开入口：

```bash
python3 ~/.codex/skills/tavo-1-0-beta/scripts/tavo_prompt_lab.py compile --case /absolute/path/to/case.json
python3 ~/.codex/skills/tavo-1-0-beta/scripts/tavo_prompt_lab.py run --case /absolute/path/to/case.json
```

可复制的完整样例位于 `assets/templates/prompt-lab-case.json`。Agent 应为当前产物生成一个 case JSON，先执行 `compile` 检查 `warnings`、`worldbookDecisions` 和 `request.messages`，得到用户同意或已明确授权真实调用后再执行 `run`。

这两个命令都不修改预设、卡、世界书或聊天文件。`--output` 写出的 JSON 权限固定为 `0600`，且不能指向 case、引用资产或 API key 文件。

## Case 格式

顶层对象支持：

| 字段 | 要求 | 说明 |
| --- | --- | --- |
| `preset` | 必填 | Tavo native `basicPrompts + entries`、MCP get/readback envelope，或只有一个明确 order 且全部为 relative entry 的 Tavo 导出 `prompts + prompt_order` 对象/JSON 路径。 |
| `character` | 必填 | Tavo character、CCv2/CCv3 `data` envelope、Tavo `card` envelope，或 JSON 路径。 |
| `persona` | 可选 | `{name, description}` 或 JSON 路径；省略时为 `User` 和空描述。 |
| `worldbooks` | 可选 | 世界书对象/路径数组；角色卡内 `character_book` 默认也参与，可用 `includeCharacterBook: false` 关闭。 |
| `history` | 可选 | 有序 `{role, content}` 数组；`hidden: true` 的消息不进入请求。 |
| `greeting` | 可选 | `first`、`none`、`false`，或 `{source:"alternate", index:0}`。无历史且省略时默认使用 `first_mes`。 |
| `userInput` | 必填 | 当前用户输入，也是世界书扫描的当前文本。 |
| `seed` | 可选 | 用于 1–99 概率的稳定离线抽样；相同输入和 seed 得到相同结果。 |
| `ejs` | 可选 | EJS 配置；默认启用 sandbox。可设 `{mode:"sandboxed"|"off", timeoutMs:1..2000, characterId, variables:{chat:{},global:{}}}`。布尔 `true/false` 分别等价于 sandboxed/off。 |
| `macroValues` | 可选 | 给 `{{date}}`、`{{time}}` 等额外简单宏提供确定值；键不区分大小写。 |
| `model` | 可选于 compile，必需于真实 run | 字符串模型 ID，或 `{id, baseUrl, parameters}`；case 内 URL 还需要显式信任。 |

对象路径相对 case 文件所在目录解析。为了避免把密钥写进产物，case 中没有 API key 字段。

布尔字段必须使用 JSON `true/false`，字符串 `"false"` 不会按 truthy 值放行。入口同时限制单文件、累计资产、世界书/entry/history 数量、单段渲染文本、最终请求和 provider response 大小；超限会在分配更大拼装结果前失败。

## 拼装规则

Prompt Lab v2 固化的是现有 Skill 参考和保留请求捕获能够支持的部分：

1. 只有 `enabled=true` 且 `active=true` 的预设 entry 参与拼装。
2. `relative` entry 严格依照 `preset.entries[]` 顺序；marker 在所在位置展开 Persona、角色字段、世界书和示例。
3. `main`、`worldInfoBefore`、`personaDescription`、`charDescription`、`charPersonality`、`scenario`、`worldInfoAfter`、`dialogueExamples`、`chatHistory`、`jailbreak` 使用现有 Tavo identifier 语义。
4. `mes_example` 以 `<START>` 分块并留在 system 文本中，不伪装成真实历史消息。
5. 选中的 `first_mes` 或 alternate greeting 作为 assistant 历史消息。
6. `chatHistory` 是历史边界；它前后的 relative entry 分别进入历史前和历史后。缺少 marker 时会警告并采用明确的 v2 fallback。
7. 相邻同 role 消息在最终 OpenAI adapter 层用两个换行合并。
8. 预设 absolute 的 depth 规则为 0 在最后一条之后、1 在最后一条之前、N 继续向前。保留的 0.93 provider 捕获显示 absolute 文本会合并进目标历史槽位，由目标槽位 role 胜出；v2 按这个捕获行为模拟并发出 warning。
9. 世界书 `atDepth` 仍按自己的 `injectionRole` 作为独立注入消息；它不能与预设 absolute 混为一个对象模型。
10. depth 超过可用可见历史时，v2 丢弃该注入并警告；同 depth 多条按来源顺序，且明确标注 Tavo tie-break 未被证明。
11. 对 Tavo 导出的 `prompts + prompt_order` 兼容预设，v2 只接受单一、无歧义且全部为 relative 的 order；按 order 启用状态重建 entries，并依据保留的 Tavo 0.93 Whisper 请求捕获把 `system_prompt=false` 且兼容 role 为 system 的正文映射为 user prompt component。多 order、缺失 identifier、重复 identifier 和非 relative 注入均 fail closed。

### 世界书触发

支持 Tavo native：

- `constant` / `keyword`
- 主关键词 OR
- `none`、`andAny`、`andAll`、`notAny`、`notAll`
- `scanDepth`
- `caseSensitive`
- `matchWholeWord`
- `probability`
- `lorebookBefore`、`lorebookAfter`、`topOfExampleMessages`、`bottomOfExampleMessages`、`atDepth`
- `injectionDepth`、`injectionRole`

也会归一化当前参考明确列出的 CC/ST-compatible 字段：`keys`、`secondary_keys`、`constant`、`selective`、`before_char`、`after_char`。未知数字 position 不会被冒充为已验证映射。

扫描策略固定为“当前输入 + 前 `scanDepth` 条可见历史消息”。这是可复现的 v2 policy；Tavo 对 depth 0、hidden、裁剪、递归等所有计数边界尚无完整公开契约。非 ASCII whole-word 使用 Python Unicode 边界并警告可能与 Tavo 不同。

`worldbookDecisions` 记录每条 entry 的 `triggered`、`keyword_miss`、`secondary_miss`、`probability_miss`、`disabled` 等结果；`triggeredWorldbooks` 只保留实际注入的快捷视图。

## 宏和 EJS

v2 遵循当前官方文档和已保留请求证据确认的顺序：**同一作者字段先 EJS，成功结果再进入 `{{ }}` 宏引擎**。因此 `<%- "{{char}}" %>` 会先产出 `{{char}}`，再替换为角色名。

### EJS 执行面

本地 Lab 执行以下会参与本轮提示词的作者资产字段：

- Persona 描述；
- 角色描述、性格、场景、选中的开场白、对话示例；
- active preset prompt 与实际使用的 `basicPrompts`；
- 世界书扫描关键词和已触发条目正文。

普通历史消息和本轮 `userInput` 中形似 `<% ... %>` 的文本不会作为代码执行，只按聊天文本保留；其中的宏仍按宏规则处理。正则字段虽是 Tavo 官方 EJS surface，但正则管线不属于 Prompt Lab，v2 不执行它。

支持当前文档列出的常用子集：`<%- expr %>`、`<%= expr %>`、`<% code %>`、`<%# comment %>`、`print()`、`<%% %%>`、`-%>` 和 `<#escape-ejs>…</#escape-ejs>`；支持条件、循环、函数、JSON、RegExp、Date，以及文档列出的 lodash 风格 `_.get/has/set/unset/cloneDeep`。不实现 include、partial、自定义分隔符。

变量桥接包括：

- `getvar`、`setvar`、`incvar`、`decvar`、`delvar`；
- 默认 `chat` 与持久化语义的 `global` 两层；Lab 只在本次 case 结果内返回最终状态，不写回 Tavo；
- `local/message/initial` 映射到 chat，`cache` 读取等价于未指定 scope；
- `charName`、`userName`、`lastUserMessage`、`lastCharMessage`、`characterId`；
- 点路径和数组路径。

初始变量从 `case.ejs.variables.chat/global` 读取。最终状态、逐字段哈希/状态、变量读写记录见输出的 `ejs` 对象。字段中任意 EJS 语法/运行错误、超时、策略拒绝或结果超限时，工具采用 Tavo 文档描述的**整字段原样回退**，并回滚该字段的变量写入；回退字段列在 `ejs.unresolvedSources`。`run` 默认拒绝发送任何含 unresolved EJS 作者字段的请求，只有明确接受偏差时才可传 `--allow-unrendered-ejs`。

### 隔离边界

每个含 EJS 的字段都在短生命周期 Node 进程的新 VM context 中运行。Worker 只接收 JSON 化的模板、常量和变量状态，不注入宿主函数；禁用字符串/Wasm 代码生成，并使用 Node permission model。macOS 额外使用系统 sandbox 拒绝网络和文件写入。模板看不到 `tavo.*`、DOM、输入框、聊天消息 API、世界书 CRUD、插件 API、网络、子进程或文件系统。

这个边界是 Prompt Lab 的 prompt-only 执行器，不是 TavoJS 或浏览器运行时复刻，也不应拿来运行来源不明的通用 JavaScript。系统没有可用 Node/worker 时，相关字段会 fail closed 并原样回退；纯文本 case 不需要启动 Node。

### 后续宏

v2 展开角色/Persona/消息常用宏、日期时间宏、格式化宏、注释/转义宏，以及聊天/全局变量宏：`setvar/addvar/incvar/decvar/getvar` 和对应的 `*globalvar`。EJS helper 与变量宏共享同一份 case 状态。`macroValues` 可覆盖动态宏以获得确定测试结果。未知宏原样保留并写入 `warnings`。

当前官方角色创建说明与 JavaScript 对象说明对 `nickname` 的单聊作用范围存在冲突；v2 在普通单聊中保留 `character.name` 作为 `{{char}}`，遇到非空 nickname 时发出 `nickname_single_chat_not_applied`，等待单聊最终请求证据再收窄行为。

## 调用真实模型

推荐把 API key 放入环境变量，不要写入 case、命令参数或结果：

```bash
# Set TAVO_PROMPT_LAB_API_KEY in the current shell or secret manager first.
python3 ~/.codex/skills/tavo-1-0-beta/scripts/tavo_prompt_lab.py run \
  --case /absolute/path/to/case.json \
  --base-url https://provider.example/v1 \
  --model provider-model-id \
  --output /absolute/path/to/result.json
```

真实 `run` 不会使用 compile 的演示模型名；模型 ID 必须来自 `--model`、`case.model.id` 或 `TAVO_PROMPT_LAB_MODEL`。

也可用 `--api-key-file`，但文件必须是普通文件、不是 symlink，且权限为 `0600`。环境变量和文件中的 key 都会拒绝换行/控制字符。无鉴权本地服务可显式传 `--no-auth`。HTTP 默认只允许 loopback；非 loopback HTTP 需要显式 `--allow-insecure-http`。客户端禁止 redirect，避免 Authorization 被带往另一个 origin。

请求目标优先取显式 `--base-url`，其次取 `TAVO_PROMPT_LAB_BASE_URL`。case 属于输入数据，不能自行决定密钥发送目的地；若确实要使用 `case.model.baseUrl`，必须额外传 `--trust-case-base-url`。不要对来源不明的 case 使用这个信任开关。

`model.parameters` 会原样进入请求，但不能覆盖 `model`、`messages` 或 `stream`，也不能放入 credential/header 类字段；v2 固定 `stream=false`。base URL 可写 provider 根、`/v1`，或完整 `/chat/completions` 地址。

## 输出

两种模式都返回：

- `compatibility`：本次模拟的明确 policy、EJS 字段顺序和边界。
- `selectedGreeting`：实际选择的开场白来源，以及 `sourceContent` / `renderedContent` 两份文本。
- `worldbookDecisions` / `triggeredWorldbooks`：触发判定。
- `assemblyTrace`：预设与 absolute 注入的来源、顺序和位置。
- `ejs`：执行模式、字段计数、整字段回退来源、初始/最终 chat/global 状态，以及字段和变量 trace。
- `request`：将要发送的完整 Chat Completions body。
- `warnings`：所有近似、未支持和证据边界。

`run` 另外返回 `provider`、脱敏后的 `response` 和提取后的 `responseText`。请求 header 从不写入结果；工具还会清理已知 credential 字段、当前 API key 和 Authorization 回显。仍不要把恶意 provider 的任意响应视为可信的秘密存储载体。

## v2 边界

Prompt Lab 的 `compatibility.target` 明确是 `evidence-bounded Tavo-shaped v2 simulation`，不是逐字节复刻整个 Tavo runtime。下列项目不应在 v2 中宣称等价：

- Tavo 私有 EJS 引擎逐字节等价、跨字段执行时机的所有内部细节，以及正则字段 EJS；
- EJS 对 TavoJS、DOM、前端控制面板或插件 API 的访问；这些本来就不是 prompt-field EJS 的职责；
- sticky、cooldown、delay 的跨轮状态机；
- 世界书递归、group scoring、priority/order 竞争；
- 同 depth 多 entry 的 Tavo tie-break；
- 超出单一 relative order 证据子集的 SillyTavern/Tavo `prompts + prompt_order` 预设，包括多 order、absolute 注入和其它未抓包映射；
- 正则、长记忆、群聊 nudge、continue/impersonation；
- Advanced Rendering、TavoJS、TPG、图片、语音和其他前端行为；
- tokenizer、上下文裁剪、provider 私有 adapter 细节与真实模型品质。

碰到这些边界时，工具要警告或 fail closed。只有用户确实需要验证这些项目时，才升级到真机/上下文日志/请求捕获验证。

## 本地回归

修改 Prompt Lab 后至少执行：

```bash
python3 ~/.codex/skills/tavo-1-0-beta/scripts/test_tavo_prompt_lab.py
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py ~/.codex/skills/tavo-1-0-beta
python3 ~/.codex/skills/tavo-1-0-beta/scripts/audit_skill_skeleton.py ~/.codex/skills/tavo-1-0-beta
python3 ~/.codex/skills/tavo-1-0-beta/scripts/audit_tavo_skill.py ~/.codex/skills/tavo-1-0-beta
```

Prompt Lab 单元测试只启动 loopback virtual provider；它没有上游转发路径，不能把 fixture response 当作真实模型语义。
