<p align="center"><img src="assets/modelscope-logo.png" alt="ModelScope 魔搭社区" width="400"></p>

# ModelScope 组织成员批量添加工具

`add_members.py` 通过本机已登录的 Google Chrome，把用户名单批量添加为 ModelScope 组织的「只读」成员。支持 `admin.modelscope.ai` 与 `admin.modelscope.cn` 两个站点的组织管理页。

> **适用对象：ModelScope 组织管理员（admin）。** 本工具操作的是 ModelScope 管理后台（`admin.modelscope.ai` / `admin.modelscope.cn`）的组织成员管理页，**只有目标组织的管理员**才能使用——运行前提就是用管理员账号登录后台并打开自己组织的成员弹窗。普通成员账号没有该页面的操作权限，工具无法也无意为普通用户提供任何组织管理能力；请不要对不属于自己的组织使用。

> **先打开页面，再运行脚本。** 本工具完全依靠网页前端信息（DOM 元素）定位弹窗、搜索框和按钮，它自己**不会打开网页、也不会登录**——运行时操作的就是 Chrome 里**当前已经打开**的「组织成员」弹窗。因此必须先完成下方「准备」的第 2 步：在 Chrome 打开目标组织的组织管理页、点开「组织成员」弹窗、把角色选为「只读」，然后再运行 `run.sh` 或 `add_members.py`。成员弹窗未打开或角色不是「只读」时，脚本会直接停止并提示。

## 工作原理

- 通过 macOS AppleScript 驱动 Chrome 在组织管理页执行 JavaScript；
- 按网页 DOM 元素（弹窗、搜索框、按钮）定位并操作，不依赖屏幕坐标，改变分辨率、显示器或窗口大小通常不影响运行；
- 只复用 Chrome 的当前登录态，**不读取、不保存任何 Cookie、密码或 Token**；
- 默认试运行（dry-run）：只搜索并校验名单能否匹配到候选用户，不点击任何按钮；加上 `--apply` 才会真正添加。

## 环境要求

- **ModelScope 组织管理员账号**（能进入管理后台并对目标组织做成员管理）；
- macOS + Google Chrome；
- Chrome 菜单「查看 → 开发者 → 允许 Apple 事件中的 JavaScript」已勾选；
- 已登录 ModelScope 管理后台，并拥有目标组织的管理权限。

## 准备（运行前必做）

1. 准备用户名单文件（如 `members.txt`），每行一个用户名；空行、`#` 开头的行和重复用户名会自动忽略（格式见 `members.example.txt`）。
2. **在 Chrome 打开目标组织的组织管理页**（`https://admin.modelscope.ai/organization?name=组织名`，cn 站把 `ai` 换成 `cn`），**点开「组织成员」弹窗，并把角色选择为「只读」**——脚本只在这套已经打开的页面上工作，这一步没做脚本无法运行。

## 一键启动（推荐）

```bash
./run.sh                                  # 交互式引导：依次询问组织名、站点、名单文件，试运行
./run.sh 组织名                            # ai 站 + members.txt，试运行
./run.sh 组织名 cn                         # cn 站，试运行
./run.sh 组织名 cn members.txt --apply    # 正式添加
```

试运行结束后，脚本会提示对应的正式添加命令；确认输出无误后再加 `--apply`。

## 直接运行

```bash
python3 add_members.py members.txt --org 组织名            # 试运行
python3 add_members.py members.txt --org 组织名 --apply    # 正式添加
python3 add_members.py members.txt --org 组织名 --site cn  # cn 站
```

脚本会依次选中候选用户 → 点击「添加成员」→ 点击「确认添加成员」。状态为「已确认添加」表示最终确认按钮已被点击；请在组织成员列表中核对实际结果。

## 不同组织 / 不同站点怎么切换？

**不需要修改代码**，用运行参数即可：

| 需求 | 参数 | 说明 |
|------|------|------|
| 切换组织 | `--org 名称`（必填） | 组织管理页 URL 中 `name=` 的值，任意组织都适用 |
| 切换站点 | `--site ai` / `--site cn` | 默认 `ai`（admin.modelscope.ai）；`cn` 为 admin.modelscope.cn |

如果确实想改代码，对应位置都在 `add_members.py`：

| 想改什么 | 修改位置 |
|----------|----------|
| 站点默认值 | `main()` 中 `--site` 参数的 `default="ai"` |
| 等待时长默认值 | `main()` 中 `--delay` 参数的 `default=2.5` |
| 成员角色（当前固定校验「只读」） | `page_ready()` 中匹配 `"只读"` 文本的两处判断；同时页面上的角色选择也要同步改为对应角色 |
| 页面元素定位（后台改版导致脚本失效时） | 顶部 `BROWSER_HELPERS` 常量，以及 `search` / `candidate_state` / `click_add_button` / `confirm_add_member` 各函数中的 CSS 选择器 |

## 注意事项

- 「可添加」只代表搜索到了匹配的候选用户，**不代表其尚未是组织成员**；已存在的用户仍会出现在候选中，请自行避免重复添加。
- 角色固定为「只读」：脚本启动时会校验成员弹窗当前选择的角色，非「只读」会拒绝运行。
- 仅支持 Google Chrome（依赖 AppleScript 复用登录态）；更换浏览器需调整控制方式与页面元素定位。
- 管理后台页面结构变更（DOM 选择器变化）可能导致脚本失效，需按上表更新选择器。
- 建议始终先试运行；成员弹窗关闭或角色不正确时，脚本会停止并提示。
- 本工具面向 **ModelScope 组织管理员（admin）**：操作的是管理后台的组织成员管理页，仅供管理自己拥有权限的组织使用，请遵守 ModelScope 平台相关条款。

## 输出与安全

每次运行会在当前目录生成 `bulk-add-report-<时间戳>.json`，逐条记录处理结果。**报告包含真实用户信息，请勿提交到公开仓库**（`.gitignore` 已默认排除报告与真实名单文件）。运行过程中按 `Ctrl+C` 可随时停止。

## 文件说明

| 文件 | 说明 |
|------|------|
| `run.sh` | 一键启动脚本（交互式 / 参数直通） |
| `add_members.py` | 主脚本 |
| `members.example.txt` | 名单文件格式示例 |
| `.gitignore` | 排除运行报告与真实名单 |
| `assets/modelscope-logo.png` | README 顶部标志（取自魔搭官方品牌元素页） |
