# 贡献指南 · Contributing

感谢你关注 **灵犀 SynergyOS**！本文件说明如何在本仓库下本地开发、测试与提交。

## 1. 环境要求

- **Python**：`>=3.9`（运行时零第三方依赖）
- **推荐版本**：仓库根目录的 `.python-version` 锁定为 `3.11`，与 CI 一致。若使用 `pyenv`：

  ```bash
  pyenv install 3.11
  pyenv local 3.11   # 自动读取 .python-version
  ```

  > ⚠️ 注意：Python 3.12+ 放宽了 f-string 嵌套引号规则（PEP 701），但 CI 用 3.11。
  > 在更高版本本地能跑通、推到 CI 却 `SyntaxError` 的情况已发生过，请保持本地与 CI 版本一致。

## 2. 本地安装

```bash
pip install -e .
```

接入真实大模型时再装：`pip install -e ".[openai]"`（或 `openai`）。

## 3. 运行测试（零 token 消耗）

全部单测走 mock 引擎，**不发任何网络请求、不消耗 token**：

```bash
SYNERGYOS_FORCE_MOCK=1 python -m pytest tests/ -q
```

当前约 **55 项**单测，应全部通过。

## 4. 提交前闸门

仓库内置 `.git/hooks/pre-commit`，提交时会**自动**跑上面的单测套件；任一失败则**阻断提交**。
请勿跳过（`git commit --no-verify`）。

## 5. 代码与提交约定

- **不要提交**：`.env`（含 API Key）、运行产物（`out_*/`、`reports_*/`）、`.pytest_cache/`、`.workbuddy/`（内部工作记忆）。这些已在 `.gitignore` 忽略。
- **核心能力**：双脑协作、冷启动偏好锚定、Reflexion 反思自愈、智能节律控制、结构化验收。
- **验收稳定性**：`synergyos/core/verify.py` 的覆盖判定是「行级否定感知边界匹配」，改动请配套更新 `tests/test_core.py`。
- **用户排除要素优先级**：用户显式排除的要素（「不要 X」「只列 A B」）优先于场景模板必备要素，仅在报告中诚实标注「⏭ 已按用户要求省略」，不强制补全。相关规则集中在 `scenarios.py` 的 `verify_excludes` 与 `verify.py` 的 `_check_structural`。
- **提交信息**：用中文简述「做了什么 + 为什么」，如 `fix: 兼容 3.11 的 f-string 嵌套引号`。

## 6. 推送到远程

- 推送会触发 GitHub Actions **CI**（跑单测）与 **Pages 部署**（发布 `synergyos/demo`）。
- 如需本地预热 CI 行为：`SYNERGYOS_FORCE_MOCK=1 python -m pytest tests/ -q` 通过即等同于 CI 绿灯。
- 修改 `.github/workflows/*.yml` 后，建议先在本地用 `python3.10 -m py_compile` 校验（3.10 与 3.11 共享 f-string 限制）。

## 7. 场景扩展

新增应用场景只需在 `synergyos/core/scenarios.py` 注册一个 `Scenario`（含 `verify_markers` / `verify_excludes`），
并（如需要）补充 demo 的 `SCENARIOS` 条目即可，验证内核会自动识别，无需改分流逻辑。
