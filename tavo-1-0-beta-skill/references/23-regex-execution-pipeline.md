# Tavo 正则执行管线

本文说明 Tavo 正则对象、执行分支、聊天绑定、导入与更新，以及如何区分界面文本、送模文本和持久消息。正则不是一个统一的“改消息”开关。

## 适用版本

Tavo 1.0 普通单聊中可按以下已标定子集创作：

- `user + send`：只转换送给模型的副本，持久 user 原文不变。
- `char + receive`：assistant replacement 被持久化，后续模型历史读取 replacement。
- `char + display`：UI 显示 replacement，持久消息与后续模型历史仍使用 raw。
- `lorebook + send`：转换已经选中的 constant 世界书正文，不改世界书源对象。
- 正则字段先执行 EJS，EJS 产出的 `{{char}}` / `{{user}}` 再按宏 substitution 展开。
- 同一正则组的 entries 按存储顺序执行。
- 普通单聊 `content` 的 `user + send` 使用 newest-first depth：本轮 outgoing user 为 0，之后每增加 1 沿持久消息向前一条；`minDepth=maxDepth=N` 包含端点，已标定到 6。

以下范围不能从上述子集外推：reasoning、`sendAndDisplay` 联合分支、`editAndReceive` 的手动编辑分支、非空 `trimStrings`、`escaped` 的精确算法、跨正则组顺序、keyword 世界书扫描先后，以及 hidden、开场白、群聊和 lorebook 的 depth 计数。

Tavo 0.91 起可使用本文的 native 对象、placements、timings、substitution、导入和 MCP 工具模型；不同版本导入默认值和第三方 ST 数值映射仍要逐对象读回。

## 管线模型

```text
正则组存在
  -> 当前聊天绑定该组
  -> entry.enabled
  -> placements 选择文本通道
  -> timing 选择执行分支
  -> minDepth/maxDepth 选择消息层
  -> EJS -> 宏 substitution -> find/trim/replace
  -> 显示副本 / 送模副本 / 持久消息
```

这是作者理解模型。跨组排序、`trimStrings` 精确时机和复杂转义不能按此图推测为固定内部实现。

## Native Object

```json
{
  "name": "状态栏显示",
  "entries": [
    {
      "identifier": "status-panel-v1",
      "name": "包装状态标签",
      "findRegex": "/<status>(.*?)<\\/status>/gim",
      "replaceString": "<pre>$1</pre>",
      "trimStrings": [],
      "placements": ["char"],
      "timing": "display",
      "substitution": "none",
      "minDepth": null,
      "maxDepth": null,
      "enabled": true
    }
  ]
}
```

| Field | Meaning | Boundary |
| --- | --- | --- |
| group `name` | 正则组名称。 | 创建时应非空。 |
| `identifier` | 组内稳定标识。 | entry upsert/delete 时复用。 |
| entry `name` | 条目显示名。 | 不代替 identifier。 |
| `findRegex` | 查找表达式，可使用普通 pattern 或 `/pattern/flags` 形式。 | 引擎、全部 flags 与超时行为不应猜测。 |
| `replaceString` | 替换文本；支持 `$1` 等捕获组和 `{{match}}`。 | 宏与捕获占位符要分层测试。 |
| `trimStrings` | 替换前裁剪的字符串列表。 | 与捕获、重复匹配的精确顺序未统一。 |
| `placements` | 处理哪些文本通道。 | 不是变量 scope。 |
| `timing` | 选择显示、送模或持久分支。 | 不同 placement 组合需单测。 |
| `substitution` | 正则字段内宏替换模式。 | 不控制 find/replace 是否执行。 |
| `minDepth` / `maxDepth` | 可选消息深度；`null` 表示不设该边界。 | 不要把普通 user/send 方向外推到所有通道。 |
| `enabled` | entry 开关。 | 正则组仍须绑定当前聊天。 |

MCP create/update/upsert 提交 entry 时应给出完整字段，只有 depth 可以省略。可复现资产不要依赖隐式默认值。

## Placements

| Value | Channel | Boundary |
| --- | --- | --- |
| `user` | 用户输入和用户消息 content。 | Tavo 1.0 已标定 send 与普通 content depth。 |
| `char` | assistant message content。 | Tavo 1.0 已标定 receive 与 display。 |
| `reasoning` | assistant reasoning。 | 与 content 分离，需有真实 reasoning 的模型单测。 |
| `lorebook` | 已选中的世界书注入正文。 | constant + send 可用；keyword 扫描先后未定。 |

重要边界：

- placements 是数组，可多选。
- 没有 `system`、`preset`、`character-card` 或角色 ID placement。
- `char` 不是“所有 system/card prompt”。
- 群聊中没有 entry 级 character selector。
- ST 数值 placement 与 native 字符串 placements 是不同层；不要凭其它客户端经验补映射表。

## Timings 与三个出口

| `timing` | 显示态 | 送模态 | 持久消息 |
| --- | --- | --- | --- |
| `display` | replacement | raw | raw |
| `send` | 通常 raw | replacement | raw |
| `sendAndDisplay` | replacement | replacement | 不应假设改变 |
| `receive` | 持久结果的显示 | 后续历史读取 replacement | replacement |
| `editAndReceive` | 收到或编辑后的持久结果 | 后续历史读取 replacement | 收到与手动编辑路径都声明改写 |

三个出口必须分开理解：

1. **显示态**：气泡、Markdown 或 AR WebView 呈现的副本。
2. **送模态**：某次 provider 请求中的上下文副本。
3. **持久消息**：消息对象中保存的 `content` / `reasoning`。

因此：

- 截图变化不证明模型看到变更或数据库已改。
- 模型按隐藏文本回答不证明 UI 或持久消息改变。
- 持久消息改变不证明 AR 渲染正确。
- `sendAndDisplay` 是两个出口，不等于先写数据库再发送。
- `editAndReceive` 应使用幂等 replacement，避免每次编辑重复加工。

## Substitution

| UI 意图 | Native value | Meaning |
| --- | --- | --- |
| 不做宏替换 | `none` | 不展开宏，但仍执行正则 find/replace。 |
| 原文宏替换 | `raw` | 以 raw 路径展开宏。 |
| 转义宏替换 | `escaped` | 以 escaped 路径展开宏。 |

`none` 绝不等于“关闭这条正则”。

正则的 find、replace 和 trim 字段可以包含 EJS 与宏。同一字段按：

```text
EJS render -> {{...}} macro substitution -> regex matching/replacement
```

复杂值包含反斜杠、美元符、HTML、换行或捕获组时，要分别比较 `none/raw/escaped`。带变量写入的模板还要防止 `sendAndDisplay` 两个分支重复副作用。

## Min/Max Depth

- `minDepth`、`maxDepth` 可为 `null` 或非负整数。
- 结构本身不保证 `minDepth <= maxDepth`。
- Tavo 1.0 普通单聊 `user + send` 中，depth 0 是 outgoing user，1 是上一条持久 assistant，2 是再前一条 user，依次逐消息向前。
- `minDepth=maxDepth=N` 包含 N。

以下仍需单测：hidden、reasoning、开场白、群聊、lorebook placement、超长历史裁剪和 `minDepth > maxDepth`。

不依赖 depth 的规则优先保持 `null/null`。需要 depth 时先建立“配置值 -> 实际命中层”的项目表。

## 正则助手与视觉样式

正则助手模板可以帮助填入思维链、引用、旁白、Markdown 代码块和标签表达式，但不会替作者选择 replacement、placement、timing、substitution 或 depth。

纯视觉包装的最小配置：

```json
{
  "placements": ["char"],
  "timing": "display",
  "substitution": "none"
}
```

让 `replaceString` 输出必要 Markdown 或 HTML。只有模型也必须看到包装时才考虑 `sendAndDisplay`；只有包装必须成为聊天历史原文时才考虑 `receive` / `editAndReceive`。

正则输出 `<script>` 不保证 JavaScript 执行。AR 开关、JavaScript 设置、Markdown、HTML 转义和 WebView 生命周期仍是独立边界。

## 导入、创建、更新与读取

| Operation | TavoJS | MCP |
| --- | --- | --- |
| 列表/查找 | `tavo.regex.all()`、`find()` | `tavo_regex_search` |
| 完整读取 | `tavo.regex.get(id)` | `tavo_regex_get` |
| ST 导入 | `tavo.regex.import(payload)` | `tavo_regex_import` |
| Native 创建 | `tavo.regex.create(regex)` | `tavo_regex_create` |
| 更新组 | `tavo.regex.update(regex)` | `tavo_regex_update` |
| 单条 upsert | 无独立方法 | `tavo_regex_entry_upsert` |
| 单条删除 | 无独立方法 | `tavo_regex_entry_delete` |
| 纯文本试跑 | 无独立方法 | `tavo_regex_test` |
| 删除组 | `tavo.regex.delete(id)` | `tavo_regex_delete` |

TavoJS `all()` 返回概要；完整 entries 需要 `get()`。MCP 写入使用 read -> dry-run -> actual -> readback，并带当前 revision 与稳定 `clientRequestId`。

### ST Import

常见 ST 到 native 映射：

| ST input | Native result |
| --- | --- |
| `scriptName` | `name` |
| `findRegex` | `findRegex` |
| `replaceString` | `replaceString` |
| `trimStrings` | `trimStrings` |
| `placement: [2]` | `placements: ['char']` |
| `disabled: false` | `enabled: true` |
| `markdownOnly: false`, `promptOnly: false`, `runOnEdit: true` | `timing: 'editAndReceive'` |
| `substituteRegex: 0` | `substitution: 'none'` |
| 缺少 native identifier | 由端侧生成 identifier |

这张表不覆盖其它数值 placement、flags 或 substitution 数值。导入成功的判断标准是 native readback 符合作者意图，而不是 JSON 表面字段原样保存。

### Safe Update

1. 读取完整 regex、entries 和 revision。
2. 只改用户委托字段，保留未知字段和未修改 entries。
3. dry-run 并确认 diff。
4. 单条修改优先 entry upsert。
5. 实际写入携带当前 revision；重试复用同一个 `clientRequestId`。
6. 写后重新读取，不以成功响应代替最终状态。
7. 在一次性对象上才做 stale-revision 冲突或删除测试。

`tavo_regex_test` 只证明 find/replace 的纯文本结果，不经过聊天绑定、placement、timing、depth、模型请求、消息持久化或 AR 渲染。

## 与其它提示层的交互

### Chat Binding

正则对象存在不等于它全局生效；当前聊天必须绑定该组。审计时同时检查：

- 正则对象完整 entries；
- 当前聊天的 regex 绑定；
- UI、provider-bound messages 和持久消息三个出口。

### Worldbook

分开两个问题：

1. 世界书条目是否因 constant/keyword 条件被选中；
2. 已选中的正文是否被 `lorebook` placement 转换。

先用 constant 世界书证明 regex 转换，再单独研究 keyword 扫描先后。不要声称 user regex 能先制造世界书触发词，也不要声称 lorebook placement 会修改世界书源对象。

### Preset And Character

native placements 没有任意 preset/card/system prompt 的全局后处理器。EJS 和宏可以写在这些对象的字段中，但那属于字段渲染，不等于正则能拦截所有提示段。

### Entry Order

同一正则组 entries 按存储顺序执行。依赖链应放在同一组并读回顺序。多个正则组之间没有稳定通用排序契约，不要建立跨组强依赖。

## 作者 A/B 方法

每个结论使用至少一对隔离聊天：

- A：绑定目标正则；
- B：不绑定、禁用 entry，或使用必不匹配 pattern；
- 两边保持角色、Persona、preset、worldbook、provider、采样、历史和用户输入一致；
- 每个样本使用随机 raw/replacement marker；
- 同时设置 expected 与 forbidden marker。

分别判定：

- UI 显示什么；
- 最终 provider messages 包含什么；
- 持久消息读回什么；
- B 是否保持 raw；
- reload、chat switch 或 app restart 是否符合该 timing 的持久语义。

### Timing Matrix

| Case | A 组设计 | Acceptance |
| --- | --- | --- |
| `display` | `char + display`，模型输出 raw marker。 | UI 为 replacement；持久与下一轮历史为 raw。 |
| `send` | `user + send`，只有 replacement 才包含可回答事实。 | 模型看到 replacement；UI 与持久 user 为 raw。 |
| `sendAndDisplay` | 同一 marker 同时构造视觉与模型事实。 | UI 与模型命中；持久原文仍按该分支预期检查。 |
| `receive` | `char + receive`，模型逐字输出 raw。 | 收到后持久 content 为 replacement，reload 后仍在。 |
| `editAndReceive` | 先跑 receive，再从真实 UI 编辑回 raw。 | 收到和手动编辑两个分支都持久化 replacement。 |

### Placement Matrix

- `user`：在 user content 放唯一 marker。
- `char`：让 assistant content 输出唯一 marker，避免只出现在 reasoning。
- `reasoning`：使用确实返回 reasoning 的模型，在 reasoning/content 放不同 marker。
- `lorebook`：先用 constant 条目隔离转换，再用 keyword 条目研究触发顺序。

### Substitution Matrix

为 `none/raw/escaped` 建立除 substitution 外完全相同的规则。宏值包含：反斜杠、`$1`、花括号、小于号、引号、与号、换行和中文标点。捕获组 `$1` 与 `{{match}}` 另设无宏控制。

### Depth Matrix

建立多层交替 user/assistant 历史，每层放唯一 marker。先用 `null/null` 建立基线，再测单层 0..N、only-min、only-max、相邻边界、逆序边界，以及 hidden/reasoning/开场白/群聊的独立 case。

## 作者检查表

- 先决定目标出口：显示、送模还是持久。
- placement 只选所需通道，不把 `char` 当 system prompt。
- 纯外观 HTML 使用 `char + display`，并单独验证 AR。
- 持久清理才用 receive/editAndReceive，并保证幂等。
- `substitution: none` 不会关闭 regex replacement。
- 普通单聊 `user + send` 可使用已标定 depth；其它通道先保持 `null` 或建立项目级 A/B。
- ST import 后比较 native readback，不承诺表面字段完全保真。
- 更新前 read、dry-run，写后按 stable ID 读回。
- `tavo_regex_test` 通过不等于聊天管线通过。
- 不把一个出口、一个 placement 或一个版本的结果外推为所有组合。
