# Kmoe Manga Downloader

[![PyPI Downloads](https://static.pepy.tech/badge/kmoe-manga-downloader)](https://pepy.tech/projects/kmoe-manga-downloader) [![PyPI version](https://img.shields.io/pypi/v/kmoe-manga-downloader.svg)](https://pypi.org/project/kmoe-manga-downloader/) [![Unit Tests](https://github.com/chrisis58/kmdr/actions/workflows/unit-test.yml/badge.svg)](https://github.com/chrisis58/kmdr/actions/workflows/unit-test.yml) [![Interpretor](https://img.shields.io/badge/python-3.9+-blue)](https://www.python.org/) [![License](https://img.shields.io/badge/License-MIT-green)](https://github.com/chrisis58/kmdr/blob/main/LICENSE)

`kmdr (Kmoe Manga Downloader)` 是一个 Python 终端应用，用于从 [Kmoe](https://kxx.moe/) 网站下载漫画。它支持在终端环境下的登录、下载指定漫画及其卷，并支持回调脚本执行。

<p align="center">
  <img src="assets/kmdr-demo.gif" alt="kmdr 使用演示" width="720">
</p>

## ✨功能特性

- **现代化终端界面**: 基于 [rich](https://github.com/Textualize/rich) 构建的终端用户界面（TUI），提供进度条和菜单等现代化、美观的交互式终端界面。
- **凭证和配置管理**: 应用自动维护登录凭证和下载设置，实现一次配置、持久有效，提升使用效率。
- **高效下载的性能**:  采用 `asyncio` 并发分片下载方式，充分利用网络带宽，显著加速单个大文件的下载速度。
- **强大的高可用性**: 内置自动重试与断点续传机制，无惧网络中断，确保下载任务在不稳定环境下依然能够成功。
- **灵活的自动化接口**: 支持在每个文件下载成功后自动执行自定义回调脚本，轻松集成到您的自动化工作流。

## 🖼️ 使用场景

- **通用的加速体验**: 采用并发分片下载方式，充分地利用不同类型用户的网络带宽，提升数据传输效率，从而有效缩短下载的等待时间。
- **灵活部署与远程控制**: 支持在远端服务器或 NAS 上运行，可以在其他设备（PC、平板）上浏览，而通过简单的命令触发远程下载任务，实现浏览与存储的分离。
- **智能化自动追新**: 应用支持识别重复内容，可配合定时任务实等现无人值守下载最新的内容，轻松打造时刻保持同步的个人资料库。

## 🛠️安装应用

你可以通过 PyPI 使用 `pip` 进行安装：

```bash
pip install kmoe-manga-downloader
```

## 📋使用方法

### 1. 登录 `kmoe`

首先需要登录 `kmoe` 并保存登录状态（Cookie）。

```bash
kmdr login -u <your_username> -p <your_password>
# 或者
kmdr login -u <your_username>
```

第二种方式会在程序运行时获取登录密码，此时你输入的密码**不会显示**在终端中。

如果登录成功，会同时显示当前登录用户及配额。

### 2. 下载漫画书籍

你可以通过以下命令下载指定书籍或卷：

```bash
# 在当前目录下载第一、二、三卷
kmdr download --dest . --book-url https://kxx.moe/c/50076.htm --volume 1,2,3
# 下面命令的功能与上面相同
kmdr download -l https://kxx.moe/c/50076.htm -v 1-3
```

```bash
# 在目标目录下载全部番外篇
kmdr download --dest path/to/destination --book-url https://kxx.moe/c/50076.htm --vol-type extra -v all
# 下面命令的功能与上面相同
kmdr download -d path/to/destination -l https://kxx.moe/c/50076.htm -t extra -v all
```

#### 常用参数说明：

- `-d`, `--dest`: 下载的目标目录（默认为当前目录），在此基础上会额外添加一个为漫画名称的子目录
- `-l`, `--book-url`: 指定漫画的主页地址
- `-v`, `--volume`: 指定下载的卷，多个用逗号分隔，例如 `1,2,3` 或 `1-5,8`，`all` 表示全部
- `-t`, `--vol-type`: 卷类型，`vol`: 单行本（默认）；`extra`: 番外；`seri`: 连载话；`all`: 全部
- `-p`, `--proxy`: 代理服务器地址
- `-r`, `--retry`: 下载失败时的重试次数，默认为 3
- `-c`, `--callback`: 下载完成后的回调脚本（使用方式详见 [4. 回调函数](https://github.com/chrisis58/kmoe-manga-downlaoder?tab=readme-ov-file#4-%E5%9B%9E%E8%B0%83%E5%87%BD%E6%95%B0)）
- `--num-workers`: 最大下载并发数量，默认为 8

> 完整的参数说明可以从 `help` 指令中获取。

### 3. 查看账户状态

查看当前账户信息（账户名和配额等）：

```bash
kmdr status
```

### 4. 回调函数

你可以设置一个回调函数，下载完成后执行。回调可以是任何你想要的命令：

```bash
kmdr download -d path/to/destination --book-url https://kxx.moe/c/50076.htm -v 1-3 \
	--callback "echo '{b.name} {v.name} downloaded!' >> ~/kmdr.log"
```

> 字符串模板会直接朴素地替换，卷名或者书名可能会包含空格，推荐使用引号包含避免出现错误。

`{b.name}, {v.name}` 会被分别替换为书籍和卷的名称。常用参数：

| 变量名   | 描述           |
| -------- | -------------- |
| v.name   | 卷的名称       |
| v.page   | 卷的页数       |
| v.size   | 卷的文件大小   |
| b.name   | 对应漫画的名字 |
| b.author | 对应漫画的作者 |

> 完整的可用参数请参考 [structure.py](https://github.com/chrisis58/kmoe-manga-downloader/blob/main/src/kmdr/core/structure.py#L11) 中关于 `VolInfo` 的定义。

### 5. 持久化配置

重复设置下载的代理服务器、目标路径等参数，可能会降低应用的使用效率。所以应用也提供了通用配置的持久化命令：

```bash
kmdr config --set proxy=http://localhost:7890 dest=/path/to/destination
kmdr config -s num_workers=5 "callback=echo '{b.name} {v.name} downloaded!' >> ~/kmdr.log"
```

只需要配置一次即可对之后的所有的下载指令生效。

> 注意：这里的参数名称不可以使用简写，例如 `dest` 不可用使用 `d` 来替换。

同时，你也可以使用以下命令进行持久化配置的管理：

- `-l`, `--list-option`: 显示当前存在的各个配置
- `-s`, `--set`: 设置持久化的配置，键和值通过 `=` 分隔，设置多个配置可以通过空格间隔
- `-c`, `--clear`: 清除配置，`all`: 清除所有；`cookie`: 退出登录；`option`: 清除持久化的配置
- `-d`, `--delete`, `--unset`: 清除单项配置

> 当前仅支持部分下载参数的持久化：`num_workers`, `dest`, `retry`, `callback`, `proxy`

### 6. 镜像源切换

为了保证服务的长期可用性，并让用户能根据自己的网络环境选择最快的服务器，应用支持灵活地切换镜像源。

当您发现默认源（当前为 `kxx.moe`）访问缓慢或失效时，可以通过 `config` 命令轻松切换到其他备用镜像源：

```
kmdr config --base-url https://mox.moe
# 或者
kmdr config -b https://mox.moe
```

你可以参考 [镜像目录](./mirror/mirrors.json) 来选择合适的镜像源，如果你发现部分镜像源过时或者有缺失，欢迎贡献你的内容！

## ⚠️ 声明

- 本工具仅作学习、研究、交流使用，使用本工具的用户应自行承担风险
- 作者不对使用本工具导致的任何损失、法律纠纷或其他后果负责
- 作者不对用户使用本工具的行为负责，包括但不限于用户违反法律或任何第三方权益的行为

---

<div align=center> 
💬任何使用中遇到的问题、希望添加的功能，都欢迎提交 issue 交流！<br />
⭐ 如果这个项目对你有帮助，请给它一个星标！<br /> <br /> 
<img src="https://counter.seku.su/cmoe?name=kmdr&theme=mbs" />
</div>
