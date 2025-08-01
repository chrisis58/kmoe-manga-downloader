# Kmoe Manga Downloader

[![Unit Tests](https://github.com/chrisis58/kmdr/actions/workflows/unit-test.yml/badge.svg)](https://github.com/chrisis58/kmdr/actions/workflows/unit-test.yml) [![Interpretor](https://img.shields.io/badge/python-3.9+-blue)](https://www.python.org/) [![License](https://img.shields.io/badge/License-MIT-green)](https://github.com/chrisis58/kmdr/blob/main/LICENSE)

`kmdr (Kmoe Manga Downloader)` 是一个 Python 脚本，用于从 [Kmoe](https://kox.moe/) 网站下载漫画。它支持在终端环境下的登录、下载指定书籍及其卷，并支持回调脚本执行。

## ✨功能特性

- 以命令行参数登录网站并持久化凭证
- 支持多种方式筛选需要的内容
- 支持网站上提供的不同的下载方式
- 支持多线程下载，失败重试、断点续传
- 提供自定义的下载完成回调命令
- 提供通用配置持久化的实现

## 🛠️安装依赖

在使用本脚本之前，请确保你已经安装了项目所需要的依赖：

```bash
git clone https://github.com/chrisis58/kmoe-manga-downloader.git
cd kmoe-manga-downloader

pip install -r requirements.txt
```

## 📋使用方法

### 1. 登录 `kmoe`

首先需要登录 `kox.moe` 并保存登录状态（Cookie）。

```bash
python kmdr.py login -u <your_username> -p <your_password>
```

或者：

```bash
python kmdr.py login -u <your_username>
```

第二种方式会在程序运行时获取登录密码。如果登录成功，会同时显示当前登录用户及配额。

### 2. 下载漫画书籍

你可以通过以下命令下载指定书籍或卷：

```bash
# 在 path/to/destination 目录下载第一、二、三卷
python kmdr.py download -d path/to/destination --book-url https://kox.moe/c/50076.htm --volume 1,2,3
python kmdr.py download -d path/to/destination --book-url https://kox.moe/c/50076.htm -v 1-3
```

```bash
# 在 path/to/download/destination 目录下载全部番外篇
python kmdr.py download -d path/to/destination --book-url https://kox.moe/c/50076.htm --vol-type extra -v all
```

#### 常用参数说明：

- `-d`, `--dest`: 下载的目标目录，在此基础上会额外添加一个为书籍名称的子目录
- `-l`, `--book-url`: 指定书籍的主页地址
- `-v`, `--volume`: 指定卷的名称，多个名称使用逗号分隔，`all` 表示下载所有卷
- `-t`, `--vol-type`: 卷类型，`vol`: 单行本（默认）；`extra`: 番外；`seri`: 连载话；`all`: 全部
- `-p`, `--proxy`: 代理服务器地址
- `-r`, `--retry`: 下载失败时的重试次数
- `-c`, `--callback`: 下载完成后的回调脚本（使用方式详见 [4. 回调函数](https://github.com/chrisis58/kmoe-manga-downlaoder?tab=readme-ov-file#4-%E5%9B%9E%E8%B0%83%E5%87%BD%E6%95%B0)）
- `--num-workers`: 最大同时下载数量，默认为 1

> 完整的参数说明可以从 `help` 指令中获取。

### 3. 查看账户状态

查看当前账户信息（例如：账户名和配额等）：

```bash
python kmdr.py status
```

### 4. 回调函数

你可以设置一个回调函数，下载完成后执行。回调可以是任何你想要的命令：

```bash
python kmdr.py download -d path/to/destination --book-url https://kox.moe/c/50076.htm -v 1-3 \
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

> 完整的可用参数请参考 [structure.py](https://github.com/chrisis58/kmdr/blob/main/core/structure.py#L11) 中关于 `VolInfo` 的定义。

### 5. 持久化配置

重复设置下载的代理服务器、目标路径等参数，可能会降低脚本的使用效率。所以脚本也提供了通用配置的持久化命令：

```bash
python kmdr.py config --set proxy=http://localhost:7890 dest=/path/to/destination
python kmdr.py config -s num_workers=5 "callback=echo '{b.name} {v.name} downloaded!' >> ~/kmdr.log"
```

只需要配置一次即可对之后的所有的下载指令生效。

> 注意：这里的参数名称不可以使用简写，例如 `dest` 不可用使用 `d` 来替换。

同时，你也可以使用以下命令进行持久化配置的管理：

- `-l`, `--list-option`: 显示当前存在的各个配置
- `-s`, `--set`: 设置持久化的配置，键和值通过 `=` 分隔，设置多个配置可以通过空格间隔
- `-c`, `--clear`: 清除配置，`all`: 清除所有；`cookie`: 退出登录；`option`: 清除持久化的配置
- `-d`, `--delete`, `--unset`: 清除单项配置

> 当前仅支持部分下载参数的持久化：`num_workers`, `dest`, `retry`, `callback`, `proxy`
>

---

⭐ 如果这个项目对你有帮助，请给它一个星标！
