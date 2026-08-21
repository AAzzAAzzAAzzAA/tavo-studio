# 世界书条目语义

本文说明 Tavo 世界书条目的字段、触发逻辑、注入位置、兼容映射和作者验证方法。不要把“对象已导入”“聊天已绑定”和“正文已进入模型上下文”混成同一种成功。

## 适用版本

- Tavo 0.91 起的 native 世界书对象使用本文所列核心字段和 MCP 工具组。
- Tavo 1.0 普通单聊中，`basicPrompts.lorebook` 的 `{0}` 是激活正文插槽；缺少它时，世界书可以完成绑定和触发判断，但正文不会自动追加到对应预设位置。
- Tavo 1.0 的一个普通单聊路径已确认 `scanDepth: 2` 包含本轮输入和紧邻的一条历史消息，不会越过紧邻 assistant 继续扫描更早的 user 消息。
- 关键词触发在旧版本和不同运行环境中出现过不一致。重要项目必须在目标版本、目标预设和目标聊天中做命中与未命中 A/B，不能只看字段读回。

## Native 条目模型

```json
{
  "identifier": "amber-harbor-safety-v1",
  "name": "琥珀潮汐港安全规则",
  "content": "琥珀潮汐港只在潮位最低时开放；绿色桥灯表示结构不安全，禁止通行。",
  "enabled": true,
  "strategy": "keyword",
  "keywords": ["琥珀潮汐港", "琥珀港"],
  "secondaryKeywords": ["绿色桥灯", "最低潮位"],
  "secondaryKeywordStrategy": "andAny",
  "scanDepth": 10,
  "caseSensitive": false,
  "matchWholeWord": false,
  "injectionPosition": "lorebookAfter",
  "injectionDepth": 4,
  "injectionRole": "system",
  "probability": 100,
  "sticky": 0,
  "cooldown": 0,
  "delay": 0
}
```

核心字段：

| 字段 | 语义 |
| --- | --- |
| `identifier` | 非空稳定标识；更新或 upsert 时复用原值。 |
| `name` | UI 显示与搜索名称，不会代替正文。 |
| `content` | 条目激活后送入提示词的正文。 |
| `enabled` | 条目总开关；为 `false` 时不再讨论其它触发条件。 |
| `strategy` | `constant` 或 `keyword`。 |
| `keywords` | 主关键词列表，只在 `keyword` 策略中生效。 |
| `secondaryKeywords` | 主词命中后的次级条件。 |
| `secondaryKeywordStrategy` | 次级逻辑：`none`、`andAny`、`andAll`、`notAny`、`notAll`。 |
| `scanDepth` | 关键词扫描的消息深度，产品范围 0–1000。 |
| `caseSensitive` | 是否区分大小写。 |
| `matchWholeWord` | 是否要求完整词边界。 |
| `injectionPosition` | 正文注入位置。 |
| `injectionDepth` | `atDepth` 时使用的非负深度。 |
| `injectionRole` | `system`、`user` 或 `assistant`。 |
| `probability` | 0–100 的激活概率。 |
| `sticky` | 激活后继续保持的消息轮数；0 表示不保持。 |
| `cooldown` | 激活后的冷却轮数；0 表示无冷却。 |
| `delay` | 延迟激活的消息轮数；0 表示立即。 |

可复现资产应显式填写这些字段，不依赖导入器或版本默认值。

## 触发模型

可以把激活理解为以下概念门槛：

```text
enabled
  -> strategy / 主关键词
  -> 次级关键词逻辑
  -> probability
  -> delay / sticky / cooldown 状态
  -> injection position / role
  -> preset world-info marker 与 lorebook wrapper
```

这是作者理解模型，不保证等同于 Tavo 内部函数的精确调用顺序。概率与三个时序字段的组合先后仍应单独验证。

### `constant`

`strategy: "constant"` 表示常驻，不依赖主词或次级词。最稳妥的常驻基线是：

```json
{
  "strategy": "constant",
  "injectionPosition": "lorebookAfter",
  "injectionRole": "system",
  "probability": 100,
  "sticky": 0,
  "cooldown": 0,
  "delay": 0
}
```

常驻条目仍需要：世界书绑定到当前聊天、对应预设 marker 可用、lorebook wrapper 保留 `{0}`，以及上下文预算允许它进入请求。

### `keyword`

`strategy: "keyword"` 表示先由主关键词建立入口，再应用次级条件。主关键词列表按“任一主词可命中”使用；若项目依赖多个主词的细微边界，应做逐词对照。

令：

- `P`：任一主关键词命中。
- `A`：至少一个次级词命中。
- `L`：所有次级词命中。

| `secondaryKeywordStrategy` | 逻辑 | 语义 |
| --- | --- | --- |
| `none` | `P` | 不启用次级门槛。 |
| `andAny` | `P && A` | 主词命中，且任一次级词命中。 |
| `andAll` | `P && L` | 主词命中，且全部次级词命中。 |
| `notAny` | `P && !A` | 主词命中，且没有次级词命中。 |
| `notAll` | `P && !L` | 主词命中，且次级词没有全部命中。 |

边界：

- `none` 不是“无主关键词”，而是关闭次级条件。
- `notAny` 与 `notAll` 不等价；只命中部分次级词时，前者失败、后者成立。
- 空次级列表配合其它四种策略的求值不应靠编程语言常识猜测；没有次级条件时明确使用 `none`。
- 关键词配置正确并完成读回，不保证目标聊天一定触发；关键资产必须做运行时正负对照。

## 扫描与匹配

### `scanDepth`

`scanDepth` 按消息深度计算，不是字符数、token 数或条目数。普通单聊中已经确认的 Tavo 1.0 子集是：

- 本轮用户输入占一个扫描槽；
- `scanDepth: 2` 再包含紧邻的一条历史消息；
- 更早的消息不在该窗口内。

仍需目标项目自行确认：

- depth 0 是否只处理当前输入，或完全关闭扫描；
- hidden、reasoning、system 消息是否计入；
- 编辑、重生成、续写和群聊是否使用同一窗口；
- 历史裁剪前后如何计数。

### `caseSensitive`

- `false`：不区分大小写。
- `true`：必须匹配大小写。

中文通常不受该开关影响。Unicode 折叠、全角半角、变音符号和 locale 行为需按目标语言验证。

### `matchWholeWord`

- `true`：要求完整词边界。
- `false`：允许子串命中。

不要假设它等同于 JavaScript `\b`。中文、日文、无空格文本、连字符、下划线、标点和 emoji 周围的边界都应建立专门样本。

## 概率与时序

### `probability`

范围为 0–100。先用 100 建立确定性正例，再用 0 建立负例。1–99 需要足够多的独立 generation 才能评估分布；单次命中或未命中没有统计意义。

不要假设重生成复用随机结果，也不要假设抽样发生在 sticky/cooldown/delay 之前或之后。

### `sticky`

条目首次激活后继续保持若干“消息轮数”。它不会扩大第一次触发的扫描窗口。不要未经测试把“消息轮数”换算成 user/assistant 往返数。

### `cooldown`

控制再次激活前的冷却轮数。以下问题仍需单独验证：sticky 内容是否在冷却期间保留、概率失败是否启动冷却、重生成是否消耗轮数、聊天切换是否重置状态。

### `delay`

控制满足条件后延迟若干消息轮数再激活。延迟从哪一事件开始计数，以及等待期间条件消失是否取消，都不能靠字段名推断。

时序测试必须先建立可靠的首次触发正例，再分别测试 sticky、cooldown、delay，最后才测组合。

## 注入位置

| `injectionPosition` | 语义 | 与预设的关系 |
| --- | --- | --- |
| `lorebookBefore` | 角色描述上方。 | 使用 `worldInfoBefore` marker。 |
| `lorebookAfter` | 角色描述下方。 | 使用 `worldInfoAfter` marker。 |
| `topOfExampleMessages` | 示例对话之前。 | 位于示例消息块顶部。 |
| `bottomOfExampleMessages` | 示例对话之后。 | 位于示例消息块底部。 |
| `atDepth` | 聊天历史的指定深度。 | 不依赖角色描述或示例 marker。 |

不要把预设 entry 的 `relative` / `absolute` 枚举写进世界书 entry。

### `atDepth`

- `injectionDepth` 只在 `atDepth` 时生效。
- `injectionRole` 可为 `system`、`user`、`assistant`。
- 世界书的 depth 不应直接套用预设 absolute entry 的索引规则。
- 只看到模型复述正文，不能证明它位于精确深度或使用精确 role。

验证 `atDepth` 时，用相邻 depth 和不同 role 做单变量 A/B，并检查最终有序模型消息。

## Lorebook Wrapper 的 `{0}`

`basicPrompts.lorebook` 中的 `{0}` 是激活世界书正文的插槽：

- `[{0}]`、`世界书：\n{0}` 等写法会把正文放进 wrapper；
- wrapper 不含 `{0}` 时，只保留 literal wrapper，激活正文不会自动追加；
- 世界书绑定、trigger decision 和 entry readback 均不能替代这项检查。

自定义预设至少应保留一个 `{0}`。多个 `{0}`、转义、群聊，以及缺失或重复 world-info marker 都要另测。

## Native、CCv3 与 ST 兼容层

区分三层：

1. **Tavo native**：create/update/entry-upsert 的标准对象，也是读回审计基线。
2. **CCv3-compatible**：已定义的一组字段转换。
3. **SillyTavern-compatible import**：接受兼容对象，但并不承诺所有第三方方言字段都被保留。

已定义的兼容映射：

| CCv3-compatible 输入 | Tavo native 输出 |
| --- | --- |
| `keys` | `keywords` |
| `secondary_keys` | `secondaryKeywords` |
| `constant: true` | `strategy: "constant"` |
| `constant: false` | `strategy: "keyword"` |
| `position: "before_char"` | `injectionPosition: "lorebookBefore"` |
| `position: "after_char"` | `injectionPosition: "lorebookAfter"` |
| `selective: true` | `secondaryKeywordStrategy: "andAny"` |
| `selective: false` | `secondaryKeywordStrategy: "none"` |

兼容导入可能生成 identifier、补默认字段、改名或丢弃未支持字段。`comment`、`order`、顶层 `description` 和第三方扩展不应被假设为原样保存。

以下常见 ST 方言字段没有统一保证：`key`、`keysecondary`、`disable`、`selectiveLogic`、数字型 `position`、`useProbability`、`matchWholeWords`、以 uid 为键的 `entries`，以及 group/recursion 扩展。对这些输入必须 dry-run、实际导入、完整 get/readback 和逐字段比较。

## 创建、导入与更新

### TavoJS

- `tavo.lorebook.all()`：读取概要列表。
- `tavo.lorebook.get(id)`：读取完整对象，不存在时返回 `null`。
- `tavo.lorebook.find(name, { match })`：按 exact/prefix/suffix/contains 查找。
- `tavo.lorebook.create(lorebook)`：创建，`name` 必填。
- `tavo.lorebook.import(lorebook)`：导入兼容 `character_book`，需要用户确认。
- `tavo.lorebook.update(lorebook)`：更新，`id` 与 `name` 必填。
- `tavo.lorebook.delete(idOrObject)`：删除。

TavoJS 参数和 MCP 的 `dryRun`、`expectedRevision`、`clientRequestId` 不可混用。

### MCP

MCP tool 通过 JSON-RPC `tools/call` 调用：

| 操作 | Tool | 关键要求 |
| --- | --- | --- |
| 搜索 | `tavo_lorebook_search` | ID 未知时先按名称查找。 |
| 读取 | `tavo_lorebook_get` | 返回 revision 与完整 entries。 |
| Native 创建 | `tavo_lorebook_create` | `lorebook.name` 必填。 |
| Native 更新 | `tavo_lorebook_update` | 先读完整对象并保留未知字段。 |
| 兼容导入 | `tavo_lorebook_import` | 预期会发生规范化。 |
| 单条 upsert | `tavo_lorebook_entry_upsert` | 使用 `lorebookId` 与完整 native entry。 |
| 单条删除 | `tavo_lorebook_entry_delete` | 使用 `lorebookId` 与 `identifier`。 |

安全流程：

1. 搜索并读取目标，保存 revision 和原始 entries。
2. 只修改用户委托的字段；单条修改优先 entry upsert。
3. 用相同 payload dry-run，检查 diff、warning 和规范化结果。
4. 实际写入时携带最新 `expectedRevision` 与稳定 `clientRequestId`。
5. 再次读取，确认 revision 和逐字段结果。
6. revision 已变化时重新读取并重算修改，不覆盖并发更新。
7. 若只为测试临时绑定世界书，结束后恢复用户原绑定。

## 作者验证方法

### 成功层级

| 层级 | 能证明 | 不能证明 |
| --- | --- | --- |
| Shape pass | 字段类型、枚举和范围可接受。 | 数据已保存。 |
| Dry-run pass | 输入可解析，预览差异符合预期。 | 实际持久化。 |
| Roundtrip pass | 写后读回保留目标 native 字段。 | 正文已进入模型上下文。 |
| Binding pass | 当前聊天绑定目标世界书。 | 本轮 entry 已激活或已注入。 |
| Prompt pass | 最终模型消息包含目标正文。 | 模型一定会遵循正文。 |
| Semantic pass | 正例命中唯一事实码，负例不泄漏。 | 精确 role、位置或概率分布。 |

### 推荐 A/B

每个测试使用只存在于目标条目的随机事实码：

1. constant 正例：用户输入不含关键词，仍应出现事实码。
2. keyword 正例：只在当前输入加入一个主词，应出现事实码。
3. keyword 未命中：绑定同书但不提供关键词，不得出现事实码。
4. 未绑定对照：提供关键词但不绑定世界书，不得出现事实码。
5. 次级逻辑矩阵：分别测试主词缺失、主词+零/一/全部次级词。
6. case/whole-word 矩阵：大小写、前后缀、标点和中文邻接分开测。
7. 概率：先测 0/100，再用多个独立 generation 测中间值。
8. 时序：每轮记录消息序列，先分别测 delay、sticky、cooldown，再测组合。
9. 位置：五个位置使用不同事实码；`atDepth` 做相邻 depth 与三种 role 的 A/B。
10. wrapper：同一预设只切换 `{0}` 有无，直接比较最终模型消息。

不要把模型根据用户问题猜出的自然语言当成注入证明；使用不可猜的事实码和未绑定对照。

## 仍需保守处理的字段

读回对象可能包含 `excludeRecursion`、`preventRecursion`、`delayUntilRecursion`、`groupName`、`groupOverride`、`groupWeight`、`useGroupScoring`、`useRegex`。仅因为这些字段出现在读回中，不代表它们是稳定的作者 API。

使用这些扩展前，应在目标版本确认字段定义、写入支持、读回和模型行为。不要根据字段名补写递归、分组或正则语义。
