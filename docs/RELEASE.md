v0.3.0：独立应用窗口与搜索设置修复。

下载 **GermanJobRadar-Windows-x64.zip**，解压后双击 EXE。适用于 Windows 10/11 x64，无需安装 Python。

- 双击 EXE 打开独立窗口，不再进入普通浏览器标签页。窗口使用已安装的 Edge 或 Chrome；岗位和申请链接仍在系统默认浏览器打开。
- 关键词、岗位类型、招聘来源和扩词开关统一保存。右侧只展示下次实际查询词，支持“保存并搜索”。
- 选择正式岗位后，查询会去掉旧关键词中的 Praktikum / Intern 前缀，按选择的岗位类型生成检索条件。
- 移除容易误解的“方向筛选”及重复关键词编辑入口。旧方向一次性合并进可见关键词；历史数据和停用词保留。
- 后台刷新不会覆盖未保存编辑；多个窗口发生设置冲突时会提示。修复保存期间加入 AI 建议可能丢失的问题。

验证包括141项 Python 测试、前端保存并发回归测试，以及 EXE 无外部 Python 启动、配置持久化、CSV、重启检查。GitHub Actions 在测试和打包检查通过后上传下载文件。

自动搜索仍可在应用中启用并修改，默认德国工作日18:00。数据保留在本机，更新时先退出应用再替换 EXE。当前 EXE 未签名。

[中文使用说明](https://github.com/ZzzGenjicat/german-job-radar/blob/main/docs/USAGE.zh-CN.md) · [Windows 说明](https://github.com/ZzzGenjicat/german-job-radar/blob/main/docs/WINDOWS.md)
