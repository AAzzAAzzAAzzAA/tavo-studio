# Tavo Prompt Lab v2.3

Prompt Lab 是本 Skill 内置的纯文本测试入口。它把 Tavo native 预设、角色卡、Persona、世界书、正则组、聊天历史和本轮输入编译成 OpenAI-compatible Chat Completions 请求；`compile` 只展示最终请求，`run` 执行单轮或固定批量回归，`run-turn` 每次只执行一轮并把可续接状态交回主 Agent。

它用于快速回答“这些文字在 Tavo 的拼装顺序下会让模型怎么回应”。v2.3 会在本地隔离进程中先渲染作者资产里的 prompt/regex-field EJS，再运行宏、正则和提示词拼装；当 case 使用 `turns` 时，还会逐轮延续持久 user/assistant 历史和 chat/global EJS 状态。正则的送模、显示和持久副本被分开输出，避免把“模型看到什么”“界面显示什么”“下一轮保存什么”混成一份文本。它仍不连接真机、不读取 Tavo 数据库，也不处理高级前端、TavoJS、TPG、图片或语音。

## Agent 入口

公开入口：

```bash
python3 scripts/tavo_prompt_lab.py compile --case /absolute/path/to/case.json
python3 scripts/tavo_prompt_lab.py run --case /absolute/path/to/case.json
python3 scripts/tavo_prompt_lab.py run-turn --case /absolute/path/to/case.json --state-out /absolute/path/to/turn-1.state.json
```

单轮及 `run-turn` 完整样例位于 `assets/templates/prompt-lab-case.json`，固定批量回归样例位于 `assets/templates/prompt-lab-session-case.json`。Agent 应先执行 `compile` 检查 `warnings`、`worldbookDecisions`、`regex` trace 和 `request.messages`，得到用户同意或已明确授权真实调用后再执行模型请求。需要根据模型真实回复决定下一句时，默认使用 `run-turn`，主 Agent 看完这一轮结果后再构造下一轮，不得把开放式语义测试预先塞成一串无人检查的 turns。

这些命令都不修改预设、卡、世界书、正则或聊天文件。`--output` 写出的 JSON 权限固定为 `0600`，且不能指向 case、引用资产或 API key 文件。

### 测试资产只读边界

每次测试的可编辑范围与用户当前明确委托的对象完全一致：委托预设就可以改预设，委托角色卡就可以改角色卡，委托世界书、Persona、正则或多个明确对象时同理。资产类型本身没有永久只读或永久可写的特权；所有未被本轮委托的测试输入都必须逐字只读。Prompt Lab 本身只读加载全部输入，主 Agent 只能在委托范围内修改源文件。

如果未被委托的原样 fixture 阻止目标字段注入，报告真实失败、对应配置和编译结果，等待用户另给 fixture 或明确扩大编辑范围。若该 fixture 本身就是委托对象，则可在请求范围内修改并重新测试。切换 `forbidOverrides`、entry type、marker、active 状态或建立 A/B 变体同样遵守委托范围；不得对未委托资产暗改，也不得把测试临时改动冒充成用户原始配置。

## 默认验收规则

普通单聊中，如果目标只是评估预设、角色卡、Persona、世界书、受支持正则、prompt-field EJS、聊天历史和当前输入怎样影响模型的文字回复，就把 Prompt Lab 作为默认验收面。先用 `compile` 检查目标相关的 `warnings`、触发报告和 `request.messages`；没有 fail-closed 错误，且目标相关 warning 已确认不影响本次结论时，直接用 `run` 测模型反应即可。

以下情况超出 Prompt Lab 的验收范围，应直接向用户说明边界，不得把本地结果冒充成完整 Tavo 运行时结论：

- case 命中下文列出的 v2.3 未支持边界，或存在尚未接受的目标相关 warning；
- 目标本身涉及 UI、持久化、Advanced Rendering、TavoJS、TPG、媒体、Agent Loop、原生长记忆或其它应用运行时行为；
- Tavo 版本与本页支持范围不同；
- 用户明确要求检验超出纯文本模拟的行为。

## Case 格式

顶层对象支持：

| 字段 | 要求 | 说明 |
| --- | --- | --- |
| `schemaVersion` | 推荐 | 新 case 使用字符串 `"2.3"`；`2.1/2.2` 仅为兼容旧 case 并产生 warning，未知版本 fail closed。结果与状态格式统一为 v2.3。 |
| `preset` | 必填 | Tavo native `basicPrompts + entries`、Tavo 对象 envelope，或只有一个明确 order 且全部为 relative entry 的 Tavo 导出 `prompts + prompt_order` 对象/JSON 路径。 |
| `character` | 必填 | Tavo character、CCv2/CCv3 `data` envelope、Tavo `card` envelope，或 JSON 路径。 |
| `persona` | 可选 | `{name, description}` 或 JSON 路径；省略时为 `User` 和空描述。 |
| `worldbooks` | 可选 | 世界书对象/路径数组；角色卡内 `character_book` 默认也参与，可用 `includeCharacterBook: false` 关闭。 |
| `regexes` | 可选 | Tavo native 正则组对象/JSON 路径数组；组内 entry 按存储顺序执行。多个组按 case 数组顺序模拟，并警告跨组绑定顺序不属于当前支持范围。 |
| `history` | 可选 | 单轮的历史，或多轮开始前的初始历史；有序 `{role, content}` 数组，`hidden: true` 的消息不进入请求。 |
| `greeting` | 可选 | `first`、`none`、`false`，或 `{source:"alternate", index:0}`。无历史且省略时默认使用 `first_mes`。 |
| `userInput` | 单轮必填 | 当前用户输入，也是世界书扫描的当前文本；不能与 `turns` 同时出现。 |
| `turns` | 固定批量回归可选 | 非空数组，不能与顶层 `userInput/input` 同时出现。每项必须有 `userInput`，可有 `label`；离线 `compile` 的所有非末轮还必须有非空 `assistantResponse`，真实批量 `run` 禁止提供该字段并逐轮使用模型真实回复。最多 64 轮；主 Agent 驱动的开放式语义测试不要使用它。 |
| `seed` | 可选 | 用于 1–99 概率的稳定离线抽样；相同输入和 seed 得到相同结果。 |
| `ejs` | 可选 | EJS 配置；默认启用 sandbox。可设 `{mode:"sandboxed"|"off", timeoutMs:1..2000, characterId, variables:{chat:{},global:{}}}`。布尔 `true/false` 分别等价于 sandboxed/off。 |
| `macroValues` | 可选 | 给 `{{date}}`、`{{time}}` 等额外简单宏提供确定值；键不区分大小写。 |
| `model` | 可选于 compile，必需于真实 run | 字符串模型 ID，或 `{id, baseUrl, parameters}`；case 内 URL 还需要显式信任。 |
| `sessionBudgetBytes` | 可选 | 整个批量 session 或 stateful `run-turn` 链的请求+响应累计字节预算，范围 1024–67108864，默认 67108864。 |

对象路径相对 case 文件所在目录解析。为了避免把密钥写进产物，case 中没有 API key 字段。

布尔字段必须使用 JSON `true/false`，字符串 `"false"` 不会按 truthy 值放行。输入、请求、状态和输出 JSON 一律拒绝 `NaN`、`Infinity`、`-Infinity`；序列化固定使用严格 JSON。入口同时限制单文件、累计资产、世界书/entry/history 数量、单段渲染文本、最终请求、单次 provider response 和 session 总预算；超限 fail closed。

## 多轮会话

### 默认：主 Agent 逐轮驱动

开放式语义验证默认使用状态式 `run-turn`。每次命令只编译并调用一轮，返回完整请求、模型回复、触发/正则/EJS trace 和下一状态；主 Agent必须先阅读这一轮，再决定下一轮发送什么、是否换探针或停止。

```bash
python3 scripts/tavo_prompt_lab.py run-turn \
  --case /absolute/path/to/case.json \
  --state-out /absolute/path/to/turn-1.state.json \
  --base-url https://provider.example/v1

python3 scripts/tavo_prompt_lab.py run-turn \
  --case /absolute/path/to/case.json \
  --state-in /absolute/path/to/turn-1.state.json \
  --state-out /absolute/path/to/turn-2.state.json \
  --user-input '根据上一轮真实回复决定的下一句' \
  --base-url https://provider.example/v1
```

- `--state-in` 必须是非 symlink 的普通 `0600` 文件；续接时还必须同时给出新的非空 `--user-input`，工具不会静默复用 case 中第一轮的输入。`--state-out` 必须是新路径，成功时原子写入并固定为 `0600`。失败时不生成新状态，避免把空回复或失败请求误当成已推进会话。
- 状态只保存持久 history、chat/global EJS 变量、turn index、case fingerprint 和预算；不保存 base URL、header、API key 或 provider response envelope。
- 状态绑定解析后的稳定资产/config fingerprint；preset、卡、Persona、世界书、正则或稳定配置变化后，旧状态 fail closed。
- HTTP 200 但没有可提取的非空模型文字时，本轮返回非零、`stateCommitted=false`，不追加 user/assistant history，也不提交 EJS 状态。

### 固定批量回归

`compile` / `run` 仍会根据顶层 `turns` 进入旧的批量模式，用于固定探针、fixture 和确定性回归。它不是开放式语义测试的默认入口。

```json
{
  "turns": [
    {
      "label": "触发关键词",
      "userInput": "我找到了一把黄铜钥匙。",
      "assistantResponse": "离线编译时填写第一轮假定回复。"
    },
    {
      "label": "验证历史",
      "userInput": "继续说说上一轮。"
    }
  ]
}
```

- `compile` 不调用模型。为了拼出第二轮请求，它必须知道第一轮 assistant 文本，所以所有非末轮都要求 `assistantResponse`；末轮可省略。
- 批量 `run` 每轮都调用同一个真实模型，并把经受支持响应适配器提取、再经过 receive 分支得到的 persistent assistant 文本带入下一轮；case 中出现任何 `assistantResponse` 都会 fail closed，防止把假回复误称为真实多轮结果。
- 第一轮按顶层 `greeting` 处理开场白；后续轮不会再次插入开场白。
- 每轮都从上一轮 `ejs.variables.final` 延续 chat/global 状态，因此持久计数器可以观察到 `1 → 2 → 3`。状态只存在于这次 Prompt Lab 进程及结果文件中，不写回 Tavo。
- 每轮独立输出完整 `request`、世界书决策、EJS trace、变量前后状态、模型回复和警告。工具不自动重试；真实运行中途失败时会保留已经完成的轮次和失败轮请求，并返回非零状态。失败轮不会被追加进 `finalHistory`。
- 这套多轮延续是 Prompt Lab 的显式模拟策略，不代表完整应用运行时。

## 拼装规则

Prompt Lab v2.3 支持以下拼装行为：

1. 只有 `enabled=true` 且 `active=true` 的预设 entry 参与拼装。
2. `relative` entry 严格依照 `preset.entries[]` 顺序；marker 在所在位置展开 Persona、角色字段、世界书和示例。Tavo 1.0 native 世界书 marker 的非空正文在相邻块合并前保留一个结尾换行。
3. `main`、`worldInfoBefore`、`personaDescription`、`charDescription`、`charPersonality`、`scenario`、`worldInfoAfter`、`dialogueExamples`、`chatHistory`、`jailbreak` 使用现有 Tavo identifier 语义。
4. `mes_example` 以 `<START>` 分块并留在 system 文本中，不伪装成真实历史消息。
5. 选中的 `first_mes` 或 alternate greeting 作为 assistant 历史消息。
6. `chatHistory` 是历史边界；它前后的 relative entry 分别进入历史前和历史后。缺少 marker 时会警告并采用明确的 v2.3 fallback。
7. Tavo native `basicPrompts + entries` 在 Tavo 1.0 OpenAI-compatible 模式下只保留第一个前导 system 块；后续逻辑 system 块先映射为 user，再把相邻同 role 块用两个换行合并。输出中的 `adapterTrace` 会逐块记录原 role、adapter role 和是否发生转换。导出的 `prompts + prompt_order` 使用其独立的 0.93 兼容映射，不套用这条 1.0 native 规则。
8. `basicPrompts.lorebook` 是世界书 wrapper，其中 `{0}` 是已激活条目正文的插槽。wrapper 缺少 `{0}` 时，marker 仍输出 wrapper 文本，但激活的世界书正文会被丢弃；v2.3 同样丢弃并发出 `lorebook_wrapper_missing_slot`，不会替作者擅自追加正文。
9. 预设 absolute 的 depth 规则为 0 在最后一条之后、1 在最后一条之前、N 继续向前。absolute 文本会合并进目标历史槽位，由目标槽位 role 胜出；v2.3 对该兼容行为发出 warning。
10. 世界书 `atDepth` 仍按自己的 `injectionRole` 作为独立注入消息；它不能与预设 absolute 混为一个对象模型。
11. depth 超过可用可见历史时，v2.3 丢弃该注入并警告；同 depth 多条按来源顺序，Tavo 自身的同深度竞争规则不属于当前支持范围。
12. 对 Tavo 导出的 `prompts + prompt_order` 兼容预设，v2.3 只接受单一、无歧义且全部为 relative 的 order；按 order 启用状态重建 entries，并在 0.93 兼容模式下把 `system_prompt=false` 且兼容 role 为 system 的正文映射为 user prompt component。多 order、缺失 identifier、重复 identifier 和非 relative 注入均 fail closed。

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

扫描策略固定为“当前输入占一个深度槽，再取最多 `scanDepth - 1` 条之前的可见消息”；`scanDepth: 0` 暂时只扫描当前输入。`scanDepth: 2` 会扫描当前输入和紧邻的一条可见消息，不会继续命中更早消息。depth 0、hidden、裁剪、递归和其它消息类型不属于完整支持范围。非 ASCII whole-word 使用 Python Unicode 边界并警告可能与 Tavo 不同。

`worldbookDecisions` 记录每条 entry 的 `triggered`、`keyword_miss`、`secondary_miss`、`probability_miss`、`disabled` 等结果；`triggeredWorldbooks` 只保留实际注入的快捷视图。

## 正则执行管线

case 可直接引用一个或多个 Tavo native 正则组：

```json
{
  "regexes": [
    "./regex.json",
    {
      "name": "会话清理",
      "entries": [
        {
          "identifier": "strip-test-tag",
          "name": "只在送模副本移除标签",
          "findRegex": "/<test>(.*?)<\\/test>/g",
          "replaceString": "$1",
          "trimStrings": [],
          "placements": ["user"],
          "timing": "send",
          "substitution": "none",
          "minDepth": null,
          "maxDepth": null,
          "enabled": true
        }
      ]
    }
  ]
}
```

v2.3 支持以下 Tavo 1.0 正则子集：

- `user` / `char` 内容分别进入正则的输入与输出 placement；`lorebook + send` 处理已经被世界书引擎选中的注入正文。
- `send` 改写 provider-bound 副本；`display` 改写 visible 副本；`receive` 与 `editAndReceive` 的接收分支改写 persistent assistant 副本。`sendAndDisplay` 分别进入送模和显示两个副本，不会因此改写持久历史。
- depth 使用 newest-first 且包含端点：本轮即将发送的 user 消息为 `0`，此前每条持久聊天消息依次为 `1`、`2`……。这项标定只覆盖普通单聊 content；hidden、reasoning、开场白、群聊与 lorebook depth 不能外推。
- 同一组内 entry 按存储顺序依次执行。多个组按 `case.regexes` 顺序模拟，但跨组绑定顺序不属于当前支持范围，因此会产生 warning。
- `findRegex`、`replaceString` 与 `trimStrings` 先按 EJS 渲染；`substitution: "raw"` 再展开 EJS 产生的普通宏。`none` 不展开普通宏，`escaped` 尚未标定。
- 多轮时，receive 后的 persistent assistant 文本进入下一轮 provider 历史；display-only 文本只出现在 `visibleHistory` / `visibleResponseText`，不会污染下一轮请求。

以下配置 fail closed，而不是静默近似：`reasoning` placement、非空 `trimStrings`、`escaped` substitution、带非空 depth 的 `lorebook` placement。JavaScript 正则仅支持当前适配器明确列出的 flags 和可由 Python 正则安全表示的语法；不支持的 flag/pattern 会直接报错。完整产品边界见 `references/23-regex-execution-pipeline.md`。

## 宏和 EJS

v2.3 的处理顺序是：**同一作者字段先 EJS，成功结果再进入 `{{ }}` 宏引擎**。因此 `<%- "{{char}}" %>` 会先产出 `{{char}}`，再替换为角色名。

### EJS 执行面

本地 Lab 执行以下会参与本轮提示词的作者资产字段：

- Persona 描述；
- 角色描述、性格、场景、选中的开场白、对话示例；
- active preset prompt 与实际使用的 `basicPrompts`；
- 世界书扫描关键词和已触发条目正文；
- 正则 entry 的 `findRegex`、`replaceString` 和 `trimStrings`。

普通历史消息和本轮 `userInput` 中形似 `<% ... %>` 的文本不会作为代码执行，只按聊天文本保留；其中的宏仍按宏规则处理。正则字段会作为作者资产渲染，但正则所处理的聊天正文不会因此被当成 EJS 代码。

支持以下常用子集：`<%- expr %>`、`<%= expr %>`、`<% code %>`、`<%# comment %>`、`print()`、`<%% %%>`、`-%>` 和 `<#escape-ejs>…</#escape-ejs>`；支持条件、循环、函数、JSON、RegExp、Date，以及 lodash 风格 `_.get/has/set/unset/cloneDeep`。不实现 include、partial、自定义分隔符。

变量桥接包括：

- `getvar`、`setvar`、`incvar`、`decvar`、`delvar`；
- 默认 `chat` 与持久化语义的 `global` 两层；Lab 只在本次 case 结果内返回最终状态，不写回 Tavo；
- `local/message/initial` 映射到 chat，`cache` 读取等价于未指定 scope；
- `charName`、`userName`、`lastUserMessage`、`lastCharMessage`、`characterId`；
- 点路径和数组路径。

初始变量从 `case.ejs.variables.chat/global` 读取。最终状态、逐字段哈希/状态、变量读写记录见输出的 `ejs` 对象。字段中任意 EJS 语法/运行错误、超时、策略拒绝或结果超限时，工具执行**整字段原样回退**，并回滚该字段的变量写入；随后仍对保留的原字段执行普通宏展开。因此失败字段中的原始 `<% ... %>` 会留下，而同字段的 `{{char}}` 仍会展开。回退字段列在 `ejs.unresolvedSources`。`run` 默认拒绝发送任何含 unresolved EJS 作者字段的请求，只有明确接受偏差时才可传 `--allow-unrendered-ejs`。

### 隔离边界

每个含 EJS 的字段都在短生命周期 Node 进程的新 VM context 中运行。Worker 只接收 JSON 化的模板、常量和变量状态，不注入宿主函数；禁用字符串/Wasm 代码生成，并使用 Node permission model。macOS 额外使用系统 sandbox 拒绝网络和文件写入。模板看不到 `tavo.*`、DOM、输入框、聊天消息 API、世界书 CRUD、插件 API、网络、子进程或文件系统。

这个边界是 Prompt Lab 的 prompt-only 执行器，不是 TavoJS 或浏览器运行时复刻，也不应拿来运行来源不明的通用 JavaScript。Prompt Lab 需要 Python 3.10 或更高版本；EJS 还需要支持 `--permission` 与 `--allow-fs-read` 的 Node.js。系统没有可用 Node/worker 时，相关字段会 fail closed 并原样回退；纯文本 case 不需要启动 Node。完整包审计会实编译两份内置模板，并在 EJS 运行时不满足要求时失败。

### 后续宏

v2.3 展开角色/Persona/消息常用宏、日期时间宏、格式化宏、注释/转义宏，以及聊天/全局变量宏：`setvar/addvar/incvar/decvar/getvar` 和对应的 `*globalvar`。EJS helper 与变量宏共享同一份 case 状态。`macroValues` 可覆盖动态宏以获得确定测试结果。未知宏原样保留并写入 `warnings`。

`nickname` 的单聊作用范围不属于当前稳定支持范围；v2.3 在普通单聊中保留 `character.name` 作为 `{{char}}`，遇到非空 nickname 时发出 `nickname_single_chat_not_applied`。

## 调用真实模型

推荐把 API key 放入环境变量，不要写入 case、命令参数或结果：

```bash
# Set TAVO_PROMPT_LAB_API_KEY in the current shell or secret manager first.
python3 scripts/tavo_prompt_lab.py run \
  --case /absolute/path/to/case.json \
  --base-url https://provider.example/v1 \
  --model provider-model-id \
  --output /absolute/path/to/result.json
```

真实 `run` 不会使用 compile 的演示模型名；模型 ID 必须来自 `--model`、`case.model.id` 或 `TAVO_PROMPT_LAB_MODEL`。

也可用 `--api-key-file`，但文件必须是普通文件、不是 symlink，且权限为 `0600`。环境变量和文件中的 key 都会拒绝换行/控制字符。无鉴权本地服务可显式传 `--no-auth`。HTTP 默认只允许 loopback；非 loopback HTTP 需要显式 `--allow-insecure-http`。客户端禁止 redirect，避免 Authorization 被带往另一个 origin。

请求目标优先取显式 `--base-url`，其次取 `TAVO_PROMPT_LAB_BASE_URL`。case 属于输入数据，不能自行决定密钥发送目的地；若确实要使用 `case.model.baseUrl`，必须额外传 `--trust-case-base-url`。不要对来源不明的 case 使用这个信任开关。

`model.parameters` 会原样进入请求，但不能覆盖 `model`、`messages` 或 `stream`，也不能放入 credential/header 类字段；v2.3 固定 `stream=false`。base URL 可写 provider 根、`/v1`，或完整 `/chat/completions` 地址。

### Provider 响应适配与停机规则

HTTP 200 不等于模型成功回复。Prompt Lab 依次接受以下明确文字面：

- Chat Completions `choices[0].message.content` 字符串或 text-block 数组；
- Completions `choices[0].text`；
- Responses `output_text` 或 `output[].content[]`；
- Anthropic Messages `content[].text`；
- `text/event-stream` 的 `data:` 文本增量；
- 明确 `Content-Type: text/plain` 的非空纯文本。

声明为 JSON 但语法损坏时，只允许从结构起点严格锚定的 `choices[0].message.content` 或顶层 `output_text` 完整字符串字段保底恢复，并写入 `nonstandard_provider_response` warning。请求回显中的 `content`、包含 error 字段的畸形体、损坏的结构化 SSE event，以及 `event: error`、JSON `error` 字段或 `type: error/response.error` 标出的 SSE error event（即使此前已有 partial text），都不能当作成功回复；HTML/error document、任意乱码或无法确认路径的字符串同样 fail closed。

提取不到非空文字时必须立即停止并返回非零：零字节或显式文字字段为空为 `empty_provider_response`，只有工具调用为 `tool_call_only_response`，没有受支持文字路径为 `unsupported_provider_response_shape`。失败结果保留脱敏、限长的 HTTP/content-type/字节数/hash/preview 诊断；结构化 JSON preview 会按 credential-like 键脱敏，任意非 JSON 正文则不进入 preview。失败轮绝不追加到会话状态。单轮 `run`、批量 `run` 和 `run-turn` 使用同一规则。

敏感参数键会先移除大小写、空格、横线、点和下划线差异再检测，因此 `api-key`、`API Key`、`x.api key` 等不能绕过。响应中的当前 API key、Bearer 值和 credential-like 键会在进入结果或状态前脱敏。

## 输出

单轮 `compile/run` 都返回：

- `compatibility`：本次模拟的明确 policy、EJS 字段顺序和边界。
- `selectedGreeting`：实际选择的开场白来源，以及 `sourceContent` / `renderedContent` 两份文本。
- `worldbookDecisions` / `triggeredWorldbooks`：触发判定。
- `assemblyTrace`：预设与 absolute 注入的来源、顺序和位置。
- `adapterTrace`：native 1.0 最终 provider role 映射前后的逐块记录。
- `ejs`：执行模式、字段计数、整字段回退来源、初始/最终 chat/global 状态，以及字段和变量 trace。
- `persistentHistory` / `persistentUserInput`：真正会延续到下一轮的原文或 receive 后文本。
- `visibleHistory` / `visibleUserInput`：应用 display 分支后的界面副本。
- `regex`：归一化后的组、depth policy，以及 send/display/lorebook/receive/response-display trace。
- `request`：将要发送的完整 Chat Completions body。
- `warnings`：所有近似、未支持和能力边界。

`run` / `run-turn` 另外返回 `provider`、`responseExtraction`、脱敏后的 `response`、模型原始 `responseText`、receive 后的 `persistentResponseText` 和 display 后的 `visibleResponseText`。请求 header 从不写入结果；工具还会清理已知 credential 字段、当前 API key 和 Authorization 回显。仍不要把恶意 provider 的任意响应视为可信的秘密存储载体。

`run-turn` 还返回 `turnIndex`、`stateCommitted` 和下一状态摘要。只有 `status=completed` 才写 `--state-out`；`provider-failed`、`blocked-before-provider` 等失败状态都返回非零且不产生推进后的状态文件。

多轮结果的顶层 `mode` 为 `compile-session` 或 `run-session`，并返回：

- `session`：总轮数、完成轮数、历史/状态/assistant 来源和不自动重试策略；
- `turns[]`：每轮完整的单轮编译字段；真实运行还含该轮 `provider`、`response`、`responseText`、`persistentResponseText`、`visibleResponseText` 和状态；离线 compile 则给出 supplied assistant 的 persistent/visible 副本；
- `finalHistory`：下一轮会继续使用的持久有序历史；
- `finalEjsVariables`：最后一轮的 chat/global 状态；
- 顶层 `warnings`：附带 `turnIndex` 的逐轮警告汇总；
- 中途失败时的 `failedTurn` 与结构化 `error`。带 `--output` 时会保留此前已完成轮次，同时进程返回非零状态。

## v2.3 边界

Prompt Lab 是 Tavo-shaped v2 纯文本模拟器，不是逐字节复刻整个 Tavo runtime。下列项目不应在 v2.3 中宣称等价：

- Tavo 私有 EJS 引擎逐字节等价，以及跨字段执行时机的所有内部细节；
- EJS 对 TavoJS、DOM、前端控制面板或插件 API 的访问；这些本来就不是 prompt-field EJS 的职责；
- sticky、cooldown、delay 的跨轮状态机；
- 世界书递归、group scoring、priority/order 竞争；
- 同 depth 多 entry 的 Tavo tie-break；
- 超出单一 relative order 支持子集的 SillyTavern/Tavo `prompts + prompt_order` 预设，包括多 order、absolute 注入和其它未支持映射；
- 正则的 reasoning、非空 trimStrings、escaped substitution、lorebook depth、跨组绑定顺序、关键词扫描先后，以及 editAndReceive 的手动编辑分支；
- 长记忆、群聊 nudge、continue/impersonation；
- Advanced Rendering、TavoJS、TPG、图片、语音和其他前端行为；
- tokenizer、上下文裁剪、其它 provider adapter 细节与真实模型品质。

碰到这些边界时，工具要警告或 fail closed，并明确告诉用户本地结果不能覆盖这些行为。

## 本地回归

修改 Prompt Lab 后至少执行：

```bash
python3 -B -m unittest scripts/test_tavo_prompt_lab.py
python3 -B -m unittest scripts/test_tavo_virtual_provider.py
```

Prompt Lab 单元测试只启动 loopback virtual provider；它没有上游转发路径，不能把 fixture response 当作真实模型语义。

当前 v2.3 回归基线是 62 条单元测试，覆盖单轮、多轮、EJS、宏、世界书、正则、provider 响应适配、状态提交和失败停机。世界书 wrapper 缺少 `{0}` 时正文被丢弃，补回 `{0}` 后 constant 与 keyword 正文均可进入请求。
