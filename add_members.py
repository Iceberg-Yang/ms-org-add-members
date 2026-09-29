#!/usr/bin/env python3
"""ModelScope 组织成员批量添加工具（只读角色）。

面向 **ModelScope 组织管理员（admin）**：通过 macOS 上已登录管理员账号的
Google Chrome，驱动 ModelScope 管理后台（admin.modelscope.ai / .cn）的组织
管理页面，把名单中的用户逐个搜索并添加为组织的「只读」成员。

特性
----
- 默认试运行（dry-run）：只搜索并校验名单，不点击任何按钮；
- 通过网页 DOM 元素（弹窗、搜索框、按钮）定位，不依赖屏幕坐标与分辨率；
- 仅复用 Chrome 当前登录态，不读取、不保存 Cookie、密码或 Token；
- 每次运行在当前目录生成 JSON 报告，逐条记录处理结果。

环境要求
--------
- macOS + Google Chrome；
- Chrome 菜单「查看 → 开发者 → 允许 Apple 事件中的 JavaScript」已勾选；
- 已登录 ModelScope 管理后台（admin.modelscope.ai 或 admin.modelscope.cn），
  并拥有目标组织的管理权限；
- 目标组织的「组织成员」弹窗已在 Chrome 中打开，且角色已选择「只读」。

用法
----
    # 一键脚本（推荐）：交互式引导，默认试运行
    ./run.sh 组织名 [ai|cn] [名单文件]

    # 试运行：校验名单能否匹配到候选用户，不添加
    python3 add_members.py members.txt --org YOUR_ORG

    # 正式添加
    python3 add_members.py members.txt --org YOUR_ORG --apply

    # 指定站点（默认 ai，即 admin.modelscope.ai；cn 站用 --site cn）
    python3 add_members.py members.txt --org YOUR_ORG --site cn
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SHORT_DELAY = 0.3
BROWSER_HELPERS = '''
const visible = element => {
  const style = getComputedStyle(element);
  const rect = element.getBoundingClientRect();
  return style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0"
    && rect.width > 0 && rect.height > 0;
};
const memberDialog = () => [...document.querySelectorAll('[role="dialog"]')]
  .find(element => visible(element) && element.textContent.includes("组织成员"));
const searchInput = () => [...document.querySelectorAll("input")]
  .find(element => visible(element) && (element.placeholder || "").includes("用户名")
    && (element.placeholder || "").includes("用户ID"));
const memberSearchTrigger = dialog => dialog
  && [...dialog.querySelectorAll('button[data-slot="popover-trigger"]')].find(visible);
'''


def apple_escape(value: str) -> str:
    return " ".join(value.splitlines()).replace("\\", "\\\\").replace('"', '\\"')


def member_dialog_check() -> str:
    return "(()=>{" + BROWSER_HELPERS + "return Boolean(memberDialog());})()"


class BrowserTab:
    """在已登录 Chrome 中定位目标组织的标签页并执行 JavaScript。

    优先使用含可见「组织成员」弹窗的标签页；仅按 URL 选择首个页面
    会在多标签页场景下误报弹窗不存在。
    """

    def __init__(self, organization_url: str) -> None:
        self.url = organization_url

    def execute(self, source: str) -> str:
        dialog_check = apple_escape(member_dialog_check())
        script = f'''tell application "Google Chrome"
  set memberDialogCheck to "{dialog_check}"
  if (count of windows) > 0 then
    if (URL of active tab of front window) starts with "{self.url}" then
      if (execute active tab of front window javascript memberDialogCheck) is "true" then
        return execute active tab of front window javascript "{apple_escape(source)}"
      end if
    end if
  end if
  repeat with windowIndex from 1 to count of windows
    repeat with tabIndex from 1 to count of tabs of window windowIndex
      if (URL of tab tabIndex of window windowIndex) starts with "{self.url}" then
        if (execute tab tabIndex of window windowIndex javascript memberDialogCheck) is "true" then
          return execute tab tabIndex of window windowIndex javascript "{apple_escape(source)}"
        end if
      end if
    end repeat
  end repeat
  if (count of windows) > 0 then
    if (URL of active tab of front window) starts with "{self.url}" then
      return execute active tab of front window javascript "{apple_escape(source)}"
    end if
  end if
  repeat with windowIndex from 1 to count of windows
    repeat with tabIndex from 1 to count of tabs of window windowIndex
      if (URL of tab tabIndex of window windowIndex) starts with "{self.url}" then
        return execute tab tabIndex of window windowIndex javascript "{apple_escape(source)}"
      end if
    end repeat
  end repeat
  error "找不到组织管理标签页：{self.url}"
end tell'''
        result = subprocess.run(
            ["osascript", "-"],
            input=script,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "无法控制 Google Chrome")
        return result.stdout.strip()

    def run(self, body: str) -> str:
        return self.execute("(()=>{" + BROWSER_HELPERS + body + "})()")

    def json(self, body: str) -> dict:
        result = self.run("return JSON.stringify((()=>{" + body + "})());")
        try:
            return json.loads(result)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"浏览器返回了无法识别的内容：{result}") from error


def javascript_value(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def load_usernames(path: Path) -> list[str]:
    seen = set()
    usernames = []
    for line in path.read_text(encoding="utf-8").splitlines():
        username = line.strip()
        if username and not username.startswith("#") and username not in seen:
            seen.add(username)
            usernames.append(username)
    return usernames


def page_ready(tab: BrowserTab) -> dict:
    return tab.json(
        '''
        const dialog = memberDialog();
        const input = searchInput();
        const trigger = memberSearchTrigger(dialog);
        const anchor = trigger || input;
        const anchorRect = anchor?.getBoundingClientRect();
        const readOnly = Boolean(anchorRect) && [...dialog.querySelectorAll("button,[role=combobox]")]
          .some(element => {
            const box = element.getBoundingClientRect();
            return visible(element) && Math.abs(box.top - anchorRect.top) < 60
              && element.textContent.includes("只读");
          });
        return {
          dialogFound: Boolean(dialog),
          triggerFound: Boolean(trigger),
          inputFound: Boolean(input),
          readOnly,
        };
        '''
    )


def open_member_search(tab: BrowserTab) -> dict:
    return tab.json(
        '''
        if (searchInput()) return {opened: true, inputReady: true};
        const trigger = memberSearchTrigger(memberDialog());
        if (!trigger) return {opened: false, error: "找不到添加成员搜索按钮"};
        trigger.click();
        return {opened: true, inputReady: false};
        '''
    )


def search(tab: BrowserTab, username: str) -> None:
    opened = open_member_search(tab)
    if not opened["opened"]:
        raise RuntimeError(opened["error"])
    if not opened["inputReady"]:
        time.sleep(SHORT_DELAY)

    tab.run(
        '''
        const input = searchInput();
        if (!input) throw new Error("找不到成员搜索框");
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
        setter.call(input, '''
        + javascript_value(username)
        + ''');
        input.focus();
        input.dispatchEvent(new Event("input", {bubbles: true}));
        input.dispatchEvent(new Event("change", {bubbles: true}));
        '''
    )


def candidate_state(tab: BrowserTab, username: str, click: bool = False) -> dict:
    return tab.json(
        '''
        const input = searchInput();
        if (!input) return {found: false, error: "成员搜索框已关闭"};
        const normalize = text => [...(text || "")].filter(char => char.trim()).join("").toLowerCase();
        const target = normalize('''
        + javascript_value(username)
        + ''');
        const inputBox = input.getBoundingClientRect();
        const options = [...document.querySelectorAll("[cmdk-item]")]
          .filter(visible)
          .filter(element => {
            const box = element.getBoundingClientRect();
            return box.top >= inputBox.bottom - 16 && box.top < inputBox.bottom + 450
              && box.left < inputBox.right && box.right > inputBox.left;
          })
          .filter(element => normalize(element.textContent).includes(target))
          .sort((left, right) => left.textContent.length - right.textContent.length);
        const candidate = options[0];
        if (candidate && '''
        + str(click).lower()
        + ''') candidate.click();
        return {
          found: Boolean(candidate),
          label: candidate?.textContent.trim().slice(0, 200) || "",
          matches: options.length,
        };
        '''
    )


def click_add_button(tab: BrowserTab) -> dict:
    return tab.json(
        '''
        const dialog = memberDialog();
        if (!memberSearchTrigger(dialog)) {
          return {clicked: false, error: "找不到添加成员搜索按钮"};
        }
        const button = [...dialog.querySelectorAll('button[aria-label="添加成员"]')].find(visible);
        if (button) button.click();
        return {
          clicked: Boolean(button),
          label: button?.getAttribute("aria-label") || "添加按钮",
        };
        '''
    )


def confirm_add_member(tab: BrowserTab) -> dict:
    return tab.json(
        '''
        const dialog = [...document.querySelectorAll('[role="dialog"]')]
          .filter(visible)
          .find(element => element.textContent.includes("确认添加成员"));
        const button = dialog && [...dialog.querySelectorAll("button")]
          .find(element => visible(element) && element.textContent.trim() === "确认添加成员");
        if (button) button.click();
        return {
          clicked: Boolean(button),
          label: button?.textContent.trim() || "确认添加成员",
        };
        '''
    )


def messages(tab: BrowserTab) -> list[str]:
    return tab.json(
        '''
        const selectors = '[role="alert"], [class*="toast"], [class*="Toast"], [class*="message"], [class*="Message"], [class*="notification"], [class*="Notification"]';
        return [...document.querySelectorAll(selectors)]
          .filter(visible)
          .map(element => element.textContent.trim())
          .filter(Boolean)
          .slice(-5);
        '''
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="通过已登录的 Chrome 将用户名批量添加到 ModelScope 组织（只读角色）。默认仅试运行。"
    )
    parser.add_argument("usernames_file", type=Path, help="UTF-8 文本文件，每行一个用户名")
    parser.add_argument("--org", required=True, help="组织名称（组织管理页 URL 中 name= 的值）")
    parser.add_argument(
        "--site",
        default="ai",
        choices=("ai", "cn"),
        help="站点后缀：ai = admin.modelscope.ai（默认），cn = admin.modelscope.cn",
    )
    parser.add_argument("--apply", action="store_true", help="实际点击添加与确认按钮")
    parser.add_argument(
        "--delay",
        type=float,
        default=2.5,
        help="搜索结果与提交完成的等待秒数，默认 2.5",
    )
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.org):
        parser.error("--org 只能包含字母、数字、点、下划线、连字符（取组织 URL 中 name= 的值）")

    if not args.usernames_file.is_file():
        parser.error(f"找不到名单文件：{args.usernames_file}")

    organization_url = f"https://admin.modelscope.{args.site}/organization?name={args.org}"
    tab = BrowserTab(organization_url)

    usernames = load_usernames(args.usernames_file)
    if not usernames:
        print("用户名文件为空。")
        return 1

    ready = page_ready(tab)
    if not ready["dialogFound"] or not ready["triggerFound"]:
        print(f"未发现成员弹窗。请在 Chrome 中打开 {args.org} 的「组织成员」弹窗后重试。")
        return 1
    if not ready["readOnly"]:
        print("请先在成员弹窗中将角色设置为「只读」，再重试。")
        return 1

    mode = "正式添加" if args.apply else "试运行（不添加）"
    print(f"{mode}：共 {len(usernames)} 个去重后的用户名，目标组织 {args.org}（{organization_url}）。")
    results = []

    for index, username in enumerate(usernames, start=1):
        try:
            search(tab, username)
            time.sleep(args.delay)
            candidate = candidate_state(tab, username, click=args.apply)
            if not candidate["found"]:
                result = {"username": username, "status": "未找到候选用户", "detail": candidate}
            elif not args.apply:
                result = {"username": username, "status": "可添加", "detail": candidate}
            else:
                time.sleep(SHORT_DELAY)
                added = click_add_button(tab)
                time.sleep(SHORT_DELAY)
                confirmed = (
                    confirm_add_member(tab)
                    if added["clicked"]
                    else {"clicked": False, "error": "未点击添加按钮"}
                )
                time.sleep(args.delay)
                result = {
                    "username": username,
                    "status": "已确认添加" if confirmed["clicked"] else "未确认添加",
                    "candidate": candidate,
                    "button": added,
                    "confirmation": confirmed,
                    "messages": messages(tab),
                }
        except Exception as error:
            result = {"username": username, "status": "错误", "detail": str(error)}

        results.append(result)
        print(f"[{index}/{len(usernames)}] {username}: {result['status']}")

        if result["status"] == "错误":
            print("脚本已停止；请检查 Chrome 页面是否仍打开成员弹窗。")
            break

    report_path = Path.cwd() / f"bulk-add-report-{datetime.now():%Y%m%d-%H%M%S}.json"
    report_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果已保存到：{report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
