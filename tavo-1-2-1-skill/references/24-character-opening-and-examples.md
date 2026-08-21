# Character Opening Messages And Examples

本文区分角色主开场白、备用问候和对话示例，并说明 TavoJS、MCP 与 CC 卡片通道的字段映射、创作职责和验证方法。

## 适用版本

- Tavo 0.91 起的 character 数据模型使用本文所列三个字段和 camelCase/snake_case 通道。
- CCv2 JSON 的三个字段可通过卡片导入保存；PNG chunk、任意第三方扩展和畸形卡不在该结论内。
- CCv3 character data 可走兼容导入或 TavoJS adapter；导入后仍要比较 native readback。
- 新 chat 可以先保持零消息；开场白通常在用户进入聊天并确认问候后才物化为 assistant message。具体 UI 流程应在目标版本复查。

## Three Different Fields

| CC/MCP field | Purpose | Visible behavior |
| --- | --- | --- |
| `first_mes` | 主开场白；建立初次场景、语气、动作密度和回应抓手。 | 新单聊问候选择中的主选项；确认后可成为首条 assistant message。 |
| `alternate_greetings` | 单聊备用开场白数组。 | 与主开场白一起供用户选择。 |
| `mes_example` | 给模型示范 `{{char}}` / `{{user}}` 的说话与互动方式。 | 不属于问候选项；按预设和上下文预算进入生成提示。 |

不要把 `mes_example` 拆成备用问候，也不要把 `alternate_greetings` 拼进 examples。

`groupOnlyGreetings` / `group_only_greetings` 是群聊专用开场白，与单聊 `alternate_greetings` 分开。

## Channel Mapping

| Meaning | TavoJS native object | MCP create/update/readback | CCv2/CCv3 data |
| --- | --- | --- | --- |
| 主开场白 | `firstMes` | `first_mes` | `data.first_mes` |
| 备用问候 | `alternateGreetings` | `alternate_greetings` | `data.alternate_greetings` |
| 对话示例 | `mesExample` | `mes_example` | `data.mes_example` |

### TavoJS Channel

- `tavo.character.get/find` 使用 `firstMes`、`alternateGreetings`、`mesExample`。
- `tavo.character.create` 要求 `name` 和 `firstMes`。
- `tavo.character.update` 要求 `id`、`name` 和 `firstMes`。
- create/update 可接受兼容的 snake_case 字段并转换为 Tavo 对象。

在 TavoJS native 对象中优先使用 camelCase。不要同时提交 camelCase 与 snake_case 同义字段；冲突优先级不应猜测。

### MCP Channel

```json
{
  "character": {
    "name": "Example",
    "description": "...",
    "first_mes": "...",
    "alternate_greetings": ["..."],
    "mes_example": "<START>\n{{user}}: ...\n{{char}}: ..."
  }
}
```

- create 使用 `name`、`description`、`first_mes`。
- `alternate_greetings` 是字符串数组。
- `mes_example` 是一个字符串，不是数组。
- update 前先读取完整角色，保留未知字段。
- MCP 参数使用 snake_case，不直接复制 TavoJS camelCase 对象。

### Card Import Channel

使用完整且单一的卡片 envelope：

```json
{
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "data": {
    "name": "Example",
    "description": "...",
    "first_mes": "...",
    "alternate_greetings": ["..."],
    "mes_example": "<START>\n{{user}}: ...\n{{char}}: ..."
  }
}
```

不要把 card envelope 传给 native character create，也不要把裸 character 对象称为一张已声明 spec 的 CC 卡。

CCv3 还可以包含 `character_book` 与 `extensions.regex_scripts`。联动导入可能创建额外资产并请求用户确认；用户只委托角色卡时，不应未经确认扩展到世界书或正则写入。

## `first_mes`

主开场白应同时完成：

- 把 `{{char}}` 和 `{{user}}` 放进具体场景；
- 用行为和台词展示角色，而不是复述设定表；
- 给用户一个可以立即回应的事件、问题、选择或冲突；
- 示范目标回复长度、排版、视角与动作密度；
- 保留用户行动主权，不替用户决定感受、选择或台词。

不要用空字符串应付必填字段。一个有效开场应能脱离设定说明单独读懂，并自然邀请下一轮互动。

`first_mes` 是高权重风格教师位。写作时直接遵守目标声口和去模板化约束，不要先生成通用 AI 腔再整体洗稿。清洗时保留事件、关系、语义强度、时序和角色意图。

## `alternate_greetings`

备用问候不是同一句换几个形容词。每一项应提供有意义的入口差异，例如：

- 不同时间或地点；
- 不同关系阶段；
- 平静、受压、回避、公开场合等不同状态；
- 不同玩法钩子或信息不对称；
- 允许用户从不同强度开始。

数组顺序应稳定；避免空项、重复项和仅替换角色名称的伪变体。

问候选择时，`{{char}}` 与 `{{user}}` 会按当前角色和 Persona 展开。当前 MCP 没有通用 greeting index/choice 参数；不要虚构 `greetingIndex` 或 `alternateGreetingId`。

## `mes_example`

多组示例写在同一字符串中，并以 `<START>` 分隔：

```text
<START>
{{user}}: 第一种情境。
{{char}}: 第一种回应。
<START>
{{user}}: 第二种情境。
{{char}}: 第二种回应。
```

创作规则：

- 使用 `{{char}}` 与 `{{user}}`，不要硬编码当前名称。
- 每个示例块前放 `<START>`。
- 用少量高区分度示例覆盖平时、受压、回避或关系变化，不要堆同质句子。
- 示例应教模型“怎么说、怎么行动、怎么留给用户回应空间”，而不是重复百科设定。
- 无声角色使用行为示例，不强造台词或口头禅。
- 示例不能替用户说话、替用户选择或强写用户内心。

`mes_example` 是否进入本轮 prompt 还取决于 preset 的 `dialogueExamples` marker、上下文预算和 provider 适配。角色对象保存成功不等于本轮模型看到了示例。

## Chat Creation And Greeting Materialization

分开理解三个动作：

1. **创建 chat**：建立会话记录，可能仍然没有消息。
2. **切换当前 chat**：让 app 打开该线程，可能出现问候选择 UI。
3. **确认问候**：把选中的主问候或备用问候物化为 assistant message。

不要在 chat create 成功后立即声称开场白已经写入，也不要把切换成功等同于问候已确认。

若用户需要完全自动化而目标版本没有无 UI 的 greeting choice 参数，应明确保留人工选择步骤；不要通过伪造第一条消息来冒充原生问候流程，除非用户明确接受这种替代。

## 作者验证方法

### Field Roundtrip

为三个字段使用互不相同的随机 marker：

```text
OPEN_MAIN_<nonce>
OPEN_ALT_A_<nonce>
EXAMPLE_ONLY_<nonce>
```

先 dry-run，再 actual create/import，最后读取角色。逐字段比较：

- 类型与数组顺序；
- 换行和 Unicode；
- `<START>`；
- 原始宏文本；
- 未委托字段是否保持不变。

导入成功但读回不一致时，记录为 normalization，不宣称完全保真。

### Main Greeting

1. 创建只绑定目标 character 与 Persona 的新 chat。
2. 确认初始消息列表为空。
3. 打开该 chat，确认选择 UI 包含主 marker。
4. 选择主问候。
5. 读取首条 assistant message，确认只含主 marker，不含备用 marker。

### Alternate Greetings

每个 alternate 使用独立新 chat。明确选择目标项后，持久 assistant message 必须包含对应 marker，且不得包含 main 或其它 alternate marker。UI 可见与消息持久化分别判定。

### Example Injection

1. 把随机 marker 只放在 `mes_example`。
2. 确认当前 preset 的 `dialogueExamples` marker 已启用。
3. 保证 marker 不在 greeting、description、scenario、worldbook、history 或用户输入中。
4. 组装一次完整模型请求，检查示例是否进入最终 messages，以及 `<START>` 如何被转换。
5. 再用未启用 examples 的控制 preset 对照。

模型可见回复复述 example marker只能作为辅助；最直接的检查是最终 prompt 中的 example block。

## 尚需项目级验证

- PNG 卡片的 chunk 和扩展兼容性；
- 任意第三方 CCv2/CCv3 方言；
- 备用问候的最大数量、空项和超长文本；
- 群聊专用 greeting 行为；
- `<START>` 转换后的精确 role、位置和多示例裁剪顺序；
- greeting choice 是否在目标版本提供新的自动化入口；
- provider 对示例消息的合并和上下文预算策略。
