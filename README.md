# Aliyun DDNS (阿里云动态域名解析)

基于 Python 的阿里云动态域名解析工具，支持同时更新 IPv4 (A 记录) 和 IPv6 (AAAA 记录)。代码规范、符合现代 CLI 标准，支持系统级服务的直接部署。

## 功能特点
- 🚀 **全面支持**: 提供对 IPv4 和 IPv6 动态解析的支持。
- 🔄 **高可用机制**: 内置数十个外部 IP 获取服务接口，拥有完善的后备重试机制。
- 🛡️ **详细日志**: 包含规范的错误输出与执行日志。
- 📦 **开箱即用**: 支持参数传递、加载独立的 JSON 配置文件，完全符合工业 CLI 工具标准。

## 安装说明

建议使用 `uv` 或者是 `pipx` 将其作为全局命令安装在系统中。在代码根目录下执行：

```bash
uv tool install .
# 或者使用 pipx install .
```
安装完成后，系统便拥有了 `aliddns-updater` 这一全局命令。

## 配置与运行

工具会优先尝试从默认的配置文件读取参数，支持的配置文件路径为：`~/.config/aliddns/config.json`。
你可以随时创建该文件并填入凭据（无需写死在代码里！）：

```json
{
    "access_key_id": "你的AccessKey_ID",
    "access_secret": "你的AccessKey_Secret",
    "domain": "example.com",
    "ipv4_prefix": "mint",
    "ipv6_prefix": "mint6"
}
```

**配置字段详细说明:**
- `access_key_id`: 你的阿里云 AccessKey ID。
- `access_secret`: 你的阿里云 AccessKey Secret。
- `domain`: 需要管理解析的主域名 (例如 `example.com`)。
- `ipv4_prefix`: IPv4 的子域名解析前缀 (例如 `@` 代表主域名本身，或 `mint`)。
- `ipv6_prefix`: IPv6 的子域名解析前缀 (例如 `ipv6`，或 `mint6`)。

### 命令行动态传参
除了配置文件，你也可以通过传参动态覆盖或者指定配置：
```bash
aliddns-updater --access-key-id LTAIxx --access-secret yyy --domain test.com --ipv4-prefix www --disable-ipv6
```
运行 `aliddns-updater --help` 可查看全部参数说明。

## 自动化运行 (Crontab 示例)
部署完毕后，你可以将它加入系统定时任务。
运行 `crontab -e` 并添加以下规则（每 10 分钟执行一次）：
```bash
*/10 * * * * ~/.local/bin/aliddns-updater >> /tmp/aliddns-updater.log 2>&1
```

*(注意：`~/.local/bin/` 是 `uv tool install` 或 `pipx` 默认的系统沙盒安装目录。如果你是通过源码直接运行，请将上述路径替换为 `cd /你的/项目/绝对路径 && uv run aliddns.py` 或使用 `which aliddns-updater` 确认工具安装的具体绝对路径。)*