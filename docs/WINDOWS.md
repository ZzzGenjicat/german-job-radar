# Windows 下载即用版

支持 Windows 10/11 x64，无需安装 Python 或管理员权限。

1. 从 [官方 Releases](https://github.com/ZzzGenjicat/german-job-radar/releases/latest) 下载 **GermanJobRadar-Windows-x64.zip**。
2. 解压整个 ZIP，放在长期保留的位置。
3. 双击 **GermanJobRadar-Windows-x64.exe**，稍等默认浏览器打开应用。
4. 修改示例关键词和搜索设置，再开始首次搜索。

也可单独下载 EXE。ZIP 附有 MIT 许可证和第三方许可；第三方许可也可在应用设置中查看。

## 自动搜索

在“搜索设置 → 自动搜索”中启用、选择时间并保存。默认周一至周五18:00，始终按德国时间运行。电脑需开机、联网并保持登录；关闭浏览器也能执行。取消开启并保存可停用。

错过时间可补抓当天未完成批次；当天已完成则不重复，手动扫描不取消定时。移动程序后，请再次保存自动搜索设置以更新路径。

## 更新和退出

数据保存在 **%LOCALAPPDATA%\GermanJobRadar**，更新 EXE 时保留。先点击右上角“退出应用”，再替换 EXE；扫描期间请等扫描完成。退出服务不会删除已启用的自动搜索计划。

关闭浏览器标签页不会停止本机服务。如果端口被占用，请先退出其他版本。源码版与下载版的数据位置不同，不会自动迁移。

## 启动问题

当前 EXE 未签名，Windows 可能提示发布者未验证。仅从官方仓库下载，可用 Release 中的 **SHA256SUMS.txt** 核对文件；请勿关闭安全软件。

启动失败可查看 **%LOCALAPPDATA%\GermanJobRadar\app.log**。报告问题前请移除日志中的个人信息。

岗位筛选、CSV 和可选 AI 的使用与隐私说明见 [中文使用说明](USAGE.zh-CN.md)。普通搜索不需要 API Key。
