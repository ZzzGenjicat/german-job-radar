# Windows 下载即用版

支持 Windows 10/11 的 64 位 x64 电脑。无需安装 Python，也无需管理员权限。

1. 在 GitHub Releases 下载 GermanJobRadar-Windows-x64.zip。
2. 解压整个 ZIP，把文件夹放在你要长期保留的位置。
3. 双击 GermanJobRadar-Windows-x64.exe，等待数秒，默认浏览器会打开本机应用。
4. 点击“搜索设置”，选择岗位类型、填写关键词，再手动抓取。首次打开不会自动搜索。

也可直接下载 EXE。ZIP 还附有 MIT 许可证、第三方许可和此说明；第三方许可也可在应用设置中查看，并在 Release 单独提供。

设置、简历、历史和日志保存在 %LOCALAPPDATA%\GermanJobRadar。更新时退出应用，然后用新 EXE 替换旧 EXE，历史会保留。下载包不带任何人的求职数据。

自动扫描：在“搜索设置”中点击“启用自动扫描”，按德国工作日18点运行。电脑必须开机、联网并保持 Windows 登录；无需一直打开浏览器。EXE 需放在固定位置，移动后重新启用。点击“停用自动扫描”可取消计划任务。

退出：页面右上角“退出应用”会停止本机服务；关闭浏览器标签页不会停止服务。扫描期间需等待扫描完成。已启用的 Windows 计划任务不会随退出删除。

如果提示端口被占用，请先退出其他安装版本。不要同时运行源码版和 EXE 版；它们的数据位置不同，不会自动混用或迁移。

下载只使用官方仓库 https://github.com/ZzzGenjicat/german-job-radar/releases 。当前 EXE 未购买商业代码签名证书；系统可能提示发布者未验证。不要关闭安全软件；可用 Release 中的 SHA256SUMS.txt 核对文件。

OpenAI 分析可选。上传简历本身只在本机提取文字；点击 AI 分析后才会按界面说明发送内容。正常检索和本机扩词不需要 API key。

启动失败时请查看 %LOCALAPPDATA%\GermanJobRadar\app.log 。
