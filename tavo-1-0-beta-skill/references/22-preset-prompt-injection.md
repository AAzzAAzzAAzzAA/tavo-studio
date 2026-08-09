# Preset Entries And Prompt Injection

本文说明 Tavo 预设的对象模型、提示词组件、注入位置、激活状态和作者验证方法。预设已保存、聊天已绑定和某条 entry 已进入最终模型请求是三个不同结论。

## 适用版本

- Tavo 0.91 起使用本文所列 `basicPrompts`、`entries`、relative/absolute、role、entry activation 与 preset activation 模型。
- Tavo 1.0 普通单聊中，`basicPrompts.lorebook` 的 `{0}` 是世界书正文插槽。自定义 wrapper 缺少 `{0}` 时，激活正文不会自动追加。
- absolute depth 0 与更早深度可以把 entry 送入模型，但精确相邻位置、超长 depth、隐藏消息计数和同深度 tie-break 仍需按目标版本检查。

## Preset Object

```js
{
  id,
  name,
  basicPrompts,
  entries
}
```

MCP 对象还可以包含 preset 级 `active`、`official`，并提供独立的 active 切换操作。

`basicPrompts` 是模板集合，例如 persona、description、personality、scenario、example-message start、chat start、group chat start、group nudge、continue nudge、impersonation 和 lorebook wrapper。

`entries` 定义实际提示组件的：

- 排列顺序；
- 启用和激活状态；
- 消息 role；
- relative 或 absolute 注入；
- 提词正文或动态 marker。

不要把 `basicPrompts` 与 `entries` 当成同一层。

## Lorebook Wrapper 的 `{0}`

默认 lorebook wrapper 使用 `{0}`。它是已激活世界书正文的格式插槽：

- wrapper 含 `{0}` 时，正文替换该插槽；
- 可以在 `{0}` 前后增加标题或边界文本；
- wrapper 不含 `{0}` 时，只保留 literal wrapper，世界书正文不会自动追加；
- 世界书绑定和触发成立，不代表模型收到了正文。

自定义预设至少保留一个 `{0}`，并在组装结果中检查正文出现次数。多个插槽、转义、群聊和缺失/重复 world-info marker 需要独立测试。

## Entry Schema

```json
{
  "identifier": "unique-id",
  "name": "Display name",
  "content": "Prompt text",
  "role": "system",
  "type": "custom",
  "injectionPosition": "relative",
  "injectionDepth": 0,
  "forbidOverrides": false,
  "enabled": true,
  "active": true
}
```

| Field | Contract |
| --- | --- |
| `identifier` | 非空稳定标识；用于定位、upsert 或删除 entry。 |
| `name` | UI 显示名，不代替 identifier。 |
| `content` | 提词正文；marker 不应依赖自定义正文。 |
| `type` | `builtin`、`marker` 或 `custom`。 |
| `role` | `system`、`user` 或 `assistant`。 |
| `injectionPosition` | `relative` 或 `absolute`。 |
| `injectionDepth` | 非负整数，只在 `absolute` 时生效。 |
| `forbidOverrides` | 禁止后续覆盖的作者意图；导入或写入可能规范化，交付前要读回核对。 |
| `enabled` | 已激活列表中的开关。 |
| `active` | 是否加入预设的激活列表；`false` 表示只存档。 |

custom entry 要进入当前提示构建，至少要求 `active=true`、`enabled=true`，且当前聊天实际使用其所属预设。

## Builtin And Marker Identifiers

| Identifier | Type | Meaning |
| --- | --- | --- |
| `main` | `builtin` | Main Prompt。 |
| `worldInfoBefore` | `marker` | 角色描述上方的世界书插入点。 |
| `personaDescription` | `marker` | Persona 描述插入点。 |
| `charDescription` | `marker` | 角色描述插入点。 |
| `charPersonality` | `marker` | 角色性格插入点。 |
| `scenario` | `marker` | 场景插入点。 |
| `enhanceDefinitions` | `builtin` | 增强角色定义。 |
| `nsfw` | `builtin` | Auxiliary Prompt，可为空。 |
| `worldInfoAfter` | `marker` | 角色描述下方的世界书插入点。 |
| `dialogueExamples` | `marker` | 对话示例插入点。 |
| `chatHistory` | `marker` | 聊天历史插入点。 |
| `jailbreak` | `builtin` | Post-History Instructions。 |

marker 是动态层的占位符。不要给 marker 的 `content` 编造运行时语义；实际内容来自 persona、character、worldbook、examples 或 history。

## Relative And Absolute

| Mode | Meaning | Depth |
| --- | --- | --- |
| `relative` | 按 `preset.entries` 数组顺序排列。 | `injectionDepth` 不生效。 |
| `absolute` | 插入聊天历史的指定深度。 | `injectionDepth` 生效。 |

absolute 的常用语义：

- `0`：最后一条消息之后；
- `1`：最后一条消息之前；
- `N`：继续向更早的历史移动。

该 depth 是提示构建深度，不是持久消息的 `index`。以下边界不能靠其它聊天软件类推：

- depth 超过可用历史长度；
- hidden 或 reasoning 是否参与计数；
- 上下文裁剪后如何计数；
- 多个 absolute entry 位于同一深度时的顺序。

## Role

`role` 描述生成上下文中的消息角色：

- `system`：系统提示组件；
- `user`：用户角色组件；
- `assistant`：助手角色组件。

它不会自动新增持久聊天消息，也不会改变角色身份。不同 provider 可能合并连续同 role 消息，因此作者应分别检查 Tavo 组装结果和最终 provider payload。

## Ordering Rules

1. Relative entry 顺序由 `preset.entries` 数组决定，不由名称、identifier 或创建时间决定。
2. Marker 也占据数组位置；移动 marker 会移动对应动态层。
3. 完整 preset update 可能覆盖整个 entries 数组。安全做法是先读取完整对象，在完整数组上修改，再更新。
4. Entry upsert 按 identifier 定位，但新 identifier 的插入位置不应靠猜测；写后读取数组顺序。
5. 导入会规范化对象。不要只看导入前 JSON 判断最终顺序、role 或开关。

## Entry Activation 与 Preset Selection

| Layer | Field or operation | Meaning |
| --- | --- | --- |
| Entry membership | `entry.active` | 是否进入该预设的激活列表。 |
| Entry switch | `entry.enabled` | 激活列表中的该 entry 是否启用。 |
| Chat binding | `chat.presetId` | 当前聊天引用哪个 preset。 |
| Library selection | preset-level `active` | 预设库当前 active 对象。 |

`chat.presetId` 与 preset-level `active` 的冲突优先级没有稳定通用结论。运行测试时：

1. 读取当前聊天的 `presetId`；
2. 读取目标 preset 的顶层 `active`；
3. 让两者指向同一 preset；
4. 测试结束后恢复原 active 选择；
5. 不把任一读回字段单独称为“已经注入”。

## 安全创建与更新

### Shape Check

- identifier 非空且组内唯一；
- type、role、position 使用有效枚举；
- depth 为非负整数；
- enabled 与 active 分开表达；
- marker 和 custom entry 不混用职责；
- lorebook wrapper 保留 `{0}`。

### Roundtrip

1. 读取修改前完整 preset 和 revision。
2. 只修改用户委托的字段；不要为了让测试通过而改动其它 preset 内容。
3. 先 dry-run，检查 diff 只有预期字段。
4. 实际写入使用最新 `expectedRevision` 和稳定 `clientRequestId`。
5. 再次读取并比较 entries 顺序、role、position、depth、enabled、active、forbidOverrides 和正文。
6. 导入路径额外记录规范化差异。

## 作者验证方法

### 隐藏 Marker A/B

1. 只在目标 preset entry 中放随机、不可猜的 marker。
2. 确保 marker 不存在于用户输入、角色卡、Persona、世界书、正则、插件、开场白或历史中。
3. 建立绑定目标 preset 的聊天 A，以及未绑定或使用中性 preset 的聊天 B。
4. A 的最终模型请求应包含 marker，B 不应包含。
5. 若只观察模型回复，同时设置 expected 与 forbidden marker，避免把偶然服从当作注入证明。

### Position、Depth 与 Role

模型复述 marker 只能证明它看到了文本。精确位置验证要比较：

- 提交对象与写后读回；
- 发送前有序历史；
- Tavo 组装后的完整 messages；
- provider 最终有序 messages 和 role；
- 相邻 depth 的单变量 A/B。

### Prompt Lab

Prompt Lab 适合检查普通单聊文本组装、relative 顺序、absolute 深度、role、世界书 wrapper 和动态层是否缺失。它不能证明未实现的高级前端、插件副作用、provider 特有消息合并或 Tavo 未覆盖的分支。

测试 preset 必须作为只读输入，除非用户本次明确委托修改 preset。若测试失败，应报告是 preset、角色卡、世界书还是其它委托对象造成，而不是偷偷调整 preset。

## 尚需项目级验证

- `chat.presetId` 与全局 active 不一致时的优先级；
- 多个 absolute entry 同 depth 的 tie-break；
- 超长 depth、hidden/reasoning 和裁剪历史的计数；
- provider 如何合并连续同 role messages；
- 多个 `{0}`、wrapper 转义、群聊和重复 marker；
- marker 缺失或禁用时的回退；
- `forbidOverrides` 在目标导入和更新路径中的最终保存值。
