# Mac mini 本地大文件方案说明

## 背景

MarkItDown 本身可以转换超过 50 MB 的文档。原项目无法上传大文件，原因
是前端和 Flask 都把上限固定为 50 MB；部署在 Vercel 时，还会先受到
Vercel Function 请求体大小的限制。

## 本次方案

本项目改为推荐在 Mac mini 上通过 `localhost + launchd` 运行：

- 服务仅监听 `127.0.0.1`，不会暴露到局域网或互联网。
- 登录 macOS 后由 LaunchAgent 自动启动，进程退出后自动重启。
- 运行副本保存在 `~/Library/Application Support/MarkItDownWebUI`，避开
  macOS 对后台进程访问 Desktop/Documents 的隐私限制。
- 默认文件上限为 500 MB，可通过环境变量调整。
- 同一时间只转换一个文档，降低大文件并发导致内存耗尽的风险。
- 上传文件与转换结果超过一小时后可由清理接口删除。
- 超限请求返回明确的 HTTP 413 和 JSON 错误信息。

## 安装

在项目目录执行：

```bash
MAX_FILE_SIZE_MB=500 ./install.sh
```

安装完成后打开：

```text
http://localhost:5001
```

首次启动时 Python 需要加载文档转换依赖，可能需要几十秒；安装脚本会等待
服务完成启动。

查看状态和日志：

```bash
./status.sh
tail -f "$HOME/Library/Application Support/MarkItDownWebUI/logs/webui.log"
```

常用控制命令：

```bash
./restart.sh
./stop.sh
./start.sh
./uninstall.sh
```

## 调整限制

例如将上限改为 750 MB：

```bash
MAX_FILE_SIZE_MB=750 ./install.sh
```

`install.sh` 会重新生成 LaunchAgent 配置并重启服务。实际可转换的文件
大小仍取决于 Mac mini 的内存、剩余磁盘空间、文件格式及文档复杂度。
拉取或修改源码后，也需要重新运行 `./install.sh`，将新版本同步到运行目录。

## 安全边界

该方案面向本机使用，不应将 Flask 端口直接开放到公网。若以后需要其他
设备访问，应另行增加身份认证、HTTPS、访问控制及上传速率限制。
