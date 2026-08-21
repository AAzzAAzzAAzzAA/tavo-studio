# EJS、TavoJS、Plugin 与 MCP 的边界

本页用于区分六条容易混淆的通道：宏、EJS、TavoJS、TPG 插件、外部 MCP 和 Agent Loop。判断一个方案时，先确定代码或文本在哪个阶段运行，再判断它能访问什么对象、效果保存在哪里。

## 适用版本

- Tavo `1.2.1` Mac：适用于本页的外部 MCP、Agent Loop、变量、文件、主题、输入框、生成、图片和 TTS 边界。
- Tavo `1.0.0`：适用于没有在 `1.2.1` 重复确认的 memory 等旧边界。
- Tavo `0.93.x`：适用于常规提示词组装、世界书、角色卡和预设文本测试。
- Tavo `0.92.x`：适用于插件根入口、兼容入口、config、Hooks 与 TTS 的细节。
- Tavo `0.91.x`：适用于高级渲染、TavoJS、世界书与消息交互的既有行为基线。

旧版本结论不能自动当成新版本保证。若交付依赖具体 UI、持久化、Hook 时序或权限行为，应在目标版本做一次最小复核。

## 六条通道总览

| 通道 | 运行阶段与宿主 | 能做什么 | 不能据此声称 |
| --- | --- | --- | --- |
| 宏 `{{...}}` | 提示词字段的宏展开；在 EJS 之后 | 注入角色、用户、场景、最近消息等上下文；读写 chat/global 变量宏 | 世界书资产 CRUD、真实输入框控制、消息 CRUD、DOM/JS、AR UI |
| EJS `<% ... %>` | 提示词组装阶段；先于宏 | 条件、循环、字符串输出、chat/global 变量 helper；可用于世界书内容及扫描关键词等提示词字段 | 浏览器 JavaScript、`tavo.*`、世界书资产 CRUD、输入框控制、消息 CRUD、插件 contribution |
| TavoJS `tavo.*` | 开启相应 WebView/JavaScript 条件后的脚本环境 | 变量、消息、聊天、世界书、输入框、文件、生成、图片与 TTS 等 API | 仅凭脚本声明保证视觉布局、确认弹窗、字段保真或重启后持久化 |
| TPG 插件 | 安装的 `.tpg` 包；manifest、根 `entry.js`、native contribution 和 scoped TavoJS facade | actions、sidebar、fragments、settings、config/i18n、chat/message/input/generation Hooks、TTS | 独立数据 API、强制权限沙箱、模型工具注册 |
| MCP | 外部 agent 通过 HTTP JSON-RPC 调用 Tavo 暴露的工具 | 世界书、聊天、消息、输入框、插件、memory、变量、文件、主题、生成、图片、TTS 和多类资产操作 | 直接运行气泡 TavoJS、保证 AR 布局、修改媒体供应商配置或获得 ASR/STT 工具 |
| Agent Loop | Tavo 把工具 schema 放进当前聊天的模型请求，并执行模型返回的 tool call | 工具发现、用户询问、网页获取、变量和多类 Tavo 对象操作 | 角色卡自带工具、外部 MCP 的同一入口、插件或角色卡注册任意模型工具 |

## 世界书读取与修改

宏或 EJS “写在世界书里”只表示：条目被拼进提示词时，其中的动态文本可以展开。它们不会因此获得世界书资产的读取、保存或删除能力。

| 原子能力 | 宏 | EJS | TavoJS | TPG | MCP |
| --- | --- | --- | --- | --- | --- |
| 在世界书提示词字段中生成动态文本 | 支持 | 支持 | 不适用 | 不适用 | 不适用 |
| 读取世界书列表或对象 | 不支持 | 不支持 | 支持 | 通过 scoped TavoJS 支持 | 支持 |
| create/import/update/delete | 不支持 | 不支持 | 支持 | 通过 scoped TavoJS 支持 | 支持 |
| 持久 import 后再次读取 | 不支持 | 不支持 | 需目标版本复核 | 需目标版本复核 | 支持 |
| 导入对象逐字段原样保存 | 不保证 | 不保证 | 不保证 | 不保证 | 不保证；Tavo 可能规范化字段 |

具体边界：

- 宏中的 `{{setvar::...}}` 修改会话变量，不是世界书条目。
- EJS 的 `getvar/setvar/incvar/decvar/delvar` 修改变量存储，不是世界书资产。
- TavoJS 提供 `tavo.lorebook.all/get/find/import/create/update/delete`。`import` 需要按产品交互处理用户确认；不要把某个动词的确认行为类推给所有动词。
- TPG 的 action 或 fragment 通过 scoped TavoJS facade 使用世界书能力。
- MCP 可通过世界书对象工具和 entry 工具读写；写入后应按稳定对象标识再次读取。
- import/create 成功不代表提交对象的未知字段、默认值或 entry identifier 会逐字保留。

## 变量与作用域

同名变量不代表同一作用域，也不代表所有通道共享访问入口。

| 通道 | 作用域与边界 |
| --- | --- |
| 宏 | chat：`setvar/addvar/incvar/decvar/getvar`；global：对应 `*globalvar` |
| EJS | `chat` 为默认；支持 `global`；`local` 兼容 chat；helper 中的 `message`/`initial` 也按 chat 处理 |
| TavoJS | `chat`、`global`、`message` 三个独立作用域 |
| TPG | action/fragment 共用 scoped `tavo.get/set/update/unset`；只有 `/messages` fragment 有当前消息上下文 |
| MCP | Tavo `1.2.1` 支持 `global`、`chat`、`message` 显式作用域的 list/get/set/update/unset；不得在作用域间静默回退 |
| Agent Loop | 可通过模型工具调用操作变量；它与外部 MCP 仍是两个入口，工具发现和权限不能互相推导 |

创作时要写清楚变量所有者和生命周期。例如“当前聊天的好感度”用 chat scope；“跨聊天的用户偏好”才考虑 global；绑定单条消息的状态使用 TavoJS message scope。EJS helper 中名为 `message` 的兼容 scope 不能当作 TavoJS 的真实 message scope。

## 输入框：get、set、append、clear、send

宏中的 `{{input}}` 是生成上下文里的最近可见用户消息，不是当前输入框文本。EJS 的 `lastUserMessage`/`lastCharMessage` 也是提示词上下文值，不是输入框 API。

| 通道 | get | set | append | clear | send |
| --- | --- | --- | --- | --- | --- |
| 宏 | 不支持 | 不支持 | 不支持 | 不支持 | 不支持 |
| EJS | 不支持 | 不支持 | 不支持 | 不支持 | 不支持 |
| TavoJS | 支持 | 支持 | 支持 | 支持 | 支持 |
| TPG | 通过 scoped TavoJS 支持 | 支持 | 支持 | 支持 | 支持 |
| MCP | 支持 | 支持 | 支持 | 支持 | 支持，走正常聊天发送流程 |

MCP 对应入口为 `tavo_input_get/set/append/clear/send`。Tavo `1.2.1` 的 get/set/append/clear 不再受当前页面限制；send 的声明仍要求聊天页，但 Mac 基线曾从设置页发送到最后活动聊天。因此 send 前必须用稳定 chat id 核对目标，不能把离开聊天页当成安全闸门。空白发送会被拒绝。

`input_append` 可能在现有文本与追加片段之间插入一个 ASCII 空格。需要精确字符串时，应在 append 后读取输入框并比较完整文本，不要假定它是无分隔符拼接。

输入框出现文本只表示 composer 已变化。只有发送并在聊天消息中出现，才表示文本进入聊天；这仍不等于模型生成成功。

## 消息 CRUD

| 通道 | Create | Read | Update | Delete |
| --- | --- | --- | --- | --- |
| 宏 | 不支持 | 只能引用少量最近消息值，不是对象读取 | 不支持 | 不支持 |
| EJS | 只能输出模板文本 | 只能使用内置最近消息常量 | 不支持 | 不支持 |
| TavoJS | `tavo.message.append` | `find/get/current/count` | `update` | `delete` |
| TPG | 通过 scoped facade 使用 `append` | `find/get/current/count` | `update` | `delete` |
| MCP | `append`；当前没有中间 `insert` | `find/get/count` | `update` | `delete` |

边界细节：

- TavoJS 没有定义 `insert`；给 `append` 传中间 index 也不能把它当 insert。
- `tavo.message.current()` 指执行脚本所在的消息气泡。TPG 只有挂在 `/messages` 的 fragment 才有 current message；`/chat` fragment、input action 和 sidebar action 中应按无当前消息处理。
- MCP 消息工具显式接收 `chatId`。目标操作优先用稳定 `id`；0-based `index` 会因追加或删除漂移。
- message append 成功不保证 UI 已正确渲染，也不保证 reasoning、hidden、characterId 等字段逐项保真。

## TPG Actions、Sidebar 与 HTML

TPG 不是另一套脚本语言。它把 manifest、native contribution、HTML 文件和入口脚本打包为 `.tpg`，实际行为通过安装后的 scoped TavoJS facade 执行。

| 能力 | 结论 | 版本边界 |
| --- | --- | --- |
| `.tpg` package、manifest 校验、安装与读取 | 支持 | `0.92.x` 基线 |
| `inputActions` 注册和处理输入框 | 支持 | `0.91.x` 起的既有行为 |
| `sidebar` 声明和 handler | 支持；视觉位置与点击需在目标版本复核 | 当前版本不得仅凭声明推断 UI 效果 |
| `htmlFragments` 注册和挂载 | 支持 | chat/message 插槽按 manifest 配置 |
| fragment 内按钮交互 | 支持脚本实现；必须单独验证目标按钮 | native action 成功不能替代 fragment 按钮测试 |
| 世界书 CRUD | 通过 scoped TavoJS 支持 | 每个写动词独立处理确认与回读 |
| 根 `entry.js` 与旧入口兼容 | 支持；双入口时 `entry` 优先 | `0.92.x` 基线 |
| `plugin.config.get/all` | 同步、只读，合并默认值与用户覆盖 | `all()` 返回浅拷贝，修改返回值不会保存 |
| input Hooks | 支持 rewrite、cancel 和 fail-open | `0.92.x` 基线 |
| generation Hooks | 支持 prepare/success/error/cancelled；来源覆盖并非全部等价 | `othersContinuation` 等路径要单独复核 |
| plugin TTS | 支持 character/persona 选择与当前聊天队列控制 | 声音身份和听感需人工确认 |

Manifest 和运行时规则：

- `contributes.inputActions` 与 `contributes.sidebar` 应配置 `entry`，通常指根 `entry.js`。旧 `scripts.actions` 是兼容入口；两者同时存在时 `entry` 优先。
- hook-only 插件可以只有 `entry`，不必声明 UI contribution。
- `contributes.htmlFragments` 指向包内 UTF-8 HTML，挂载到 chat/message 插槽；它不是远程 URL，也不自动提供任意静态资源服务。
- input/sidebar handler 与 fragment 依赖 Advanced Rendering WebView runtime。AR 关闭时，native action 可能仍可见，但脚本 handler 不能据此视为已运行。
- fragment 脚本属于已安装插件 runtime，不受聊天内容 JavaScript 执行模式控制；后者只控制角色卡、模型输出等消息气泡脚本。
- 插件入口和 fragment 使用词法 `tavo` 作为 scoped facade，不要把 `window.tavo` 或 `globalThis.tavo` 当作插件契约。
- contribution 已注册只表示 manifest 和 runtime 入口被接受，不保证菜单布局、点击、像素位置或遮挡正确。

### Hooks 与 TTS 的细节

- `input:beforeSend/afterSend` 只在 entry 注册，可覆盖 UI、TavoJS、MCP 等发送来源。错误、超时或无效返回按 fail-open；显式 cancel 才停止后续 handler。
- generation 的 prepare/success/error/cancelled 只在 entry 注册，HTML fragment 不能注册。`prepare` 的改写进入当次 provider 请求，但不应默认改写已保存的用户消息；`success` 发生在助手消息保存前。
- 流式中间状态不能当作多次持久 assistant add；具体消息事件与 `message:changed` 的顺序应按目标版本复核。
- `tavo.input.send()` 返回的是接受阶段结果；没有观察到某个失败 reason，不代表该 reason 不存在。
- `tavo.tts.play` 必须显式选择 character/persona；`stop` 控制共享的当前聊天队列。程序状态正常不代表声音角色或听感正确。

## 权限、确认与安全

### 宏与 EJS

- 宏/EJS 在提示词渲染阶段运行，不应设计成依赖逐次权限弹窗的事务。
- EJS 可在兼容性设置中关闭。模板错误时，字段可能回退为未渲染文本；“原文仍在”不代表模板部分执行成功。
- 宏/EJS 没有 TPG manifest permissions，也没有 MCP access scope。

### TavoJS

- 消息内容中的 TavoJS 依赖相应 AR/JavaScript 设置，并可能触发风险确认。
- 世界书 import 和其它持久写操作应按产品交互处理确认。不要根据 create 的表现推断 update/delete 一定相同。
- 破坏性、昂贵或外部动作可能受确认设置约束；每个 API 的行为单独判断。

### TPG

- 插件可包含脚本和 UI fragment，只安装可信包。启用成功不等于代码安全。
- `manifest.permissions` 表达作者意图；在已知版本中不能把它当成完整的强制沙箱。
- 权限声明少不保证调用会被阻止；声明完整也不表示用户已批准每次持久写入。

### MCP

- MCP Server 默认关闭；启用时使用 access scope 和 bearer token。token 不得写入角色卡、世界书、聊天、截图、日志或公开 issue。
- 写操作只使用当前 schema 明确暴露的控制字段。Tavo `1.2.1` 不应泛化附带旧 `expectedRevision`；推荐顺序是读取目标、构造最小 patch、在支持时 dry-run、执行写入、按稳定标识回读。
- access scope 允许连接不等于用户批准每次破坏性写操作。删除、覆盖、重置、卸载等操作必须有明确委托。

## 高级渲染结论边界

视觉验证只能说明当时屏幕中的 WebView、面板、按钮、状态文本和输入框效果。它不能自动说明：

- TPG fragment 内另一颗按钮也可点击；
- TavoJS 的所有 input/message/worldbook 方法都成功；
- global/message 变量跨重启持久；
- 导入导出逐字段保真；
- 不同屏幕尺寸、滚动位置和聊天切换后都没有遮挡；
- fixed、sticky、z-index、overflow 等 CSS 组合在所有设备一致。

反过来，对象读取、API 返回或 DOM 结构也不能替代视觉检查。涉及布局、点击目标、遮挡和滚动时，必须检查实际渲染结果。

## 不可替代规则

1. API 或工具入口存在，不代表调用权限、确认流程、参数、最终效果和持久化都正确。
2. schema、manifest 校验、打包成功或 `dryRun` 只表示形状或预览可接受，不代表真实写入。
3. 写调用返回 success 后，仍要按稳定 id 或 revision 检查最终对象。
4. 对象状态正确不代表 AR 视觉、native 菜单、点击目标或 CSS 布局正确。
5. 输入框 set/append 不代表 send；send 不代表直接消息 CRUD；消息保存不代表模型生成成功。
6. 世界书 import 不代表 update/delete，也不保证 entry 逐字段保真或关键词触发语义。
7. plugin contribution 注册不代表 handler 完成、fragment 可见或 sidebar 可用。
8. chat 变量可用不代表 global/message scope 可用；EJS 的兼容 scope 也不能替代 TavoJS scope。
9. MCP 工具成功不能替代同名 TavoJS API 测试；TPG handler 成功不能替代角色卡气泡中的 TavoJS 生命周期测试。
10. Create、Read、Update、Delete 四个动词分别验证，不能互相代替。

## 社区版创作与验证方法

1. 先写明目标效果属于提示词文本、输入框、持久对象、插件 runtime、模型工具调用还是可视 UI。
2. 选择唯一正确通道；不要用 EJS 模拟 TavoJS，也不要把 MCP 当成 AR 浏览器。
3. 每次只测一个原子行为，并使用唯一、无歧义的临时 marker。
4. 在效果真正落点检查结果：提示词看模型输入，输入框看 composer，对象写入按稳定标识读取，视觉效果看实际渲染。
5. 多轮测试由主 Agent 一轮一轮观察后再决定下一条消息，避免批量发送掩盖首轮偏差。
6. 明确记录适用版本和未覆盖边界；测试通过不得扩大成整个通道或其它版本都通过。

项目专用的外部 MCP 客户端与插件实现不属于本页范围。本页只描述 Tavo 原生边界，以及 MCP、TPG、TavoJS、EJS、宏、Agent Loop 与 Advanced Rendering 之间不可互相替代的职责。
