# Kmoe Manga Downloader

[![Unit Tests](https://github.com/chrisis58/kmdr/actions/workflows/unit-test.yml/badge.svg)](https://github.com/chrisis58/kmdr/actions/workflows/unit-test.yml) [![Interpretor](https://img.shields.io/badge/python-3.9+-blue)](https://www.python.org/) [![License](https://img.shields.io/badge/License-MIT-green)](https://github.com/chrisis58/kmdr/blob/main/LICENSE)

`kmdr (Kmoe Manga Downloader)` 是一个 Python 脚本，用于从 [Kmoe](https://kox.moe/) 网站下载漫画。它支持在终端环境下的登录、下载指定书籍及其卷，并支持回调脚本执行。

## 功能

- 以命令行参数登录网站并持久化凭证
- 支持多种方式筛选需要的内容
- 支持网站上提供的不同的下载方式
- 支持多线程下载，失败重试、断点续传
- 提供自定义的下载完成回调命令

## 安装依赖

在使用本脚本之前，请确保你已经安装了项目所需要的依赖：

```bash
git clone https://github.com/chrisis58/kmdr.git
cd kmdr

pip install -r requirements.txt
```

## 使用方法

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
- `--book-url`: 指定书籍的主页地址
- `-v`, `--volume`: 指定卷的名称，多个名称使用逗号分隔，`all` 表示下载所有卷
- `--vol-type`: 卷类型，`vol`: 单行本（默认）；`extra`: 番外；`seri`: 连载话；`all`: 全部
- `-p`, `--proxy`: 代理服务器地址
- `-r`, `--retry`: 下载失败时的重试次数
- `--callback`, `-c`: 下载完成后的回调脚本（使用方式详见 [4. 回调函数](# 4. 回调函数)）

> 完整的参数说明可以从 `help` 指令中获取。

### 3. 查看账户状态

查看当前账户信息（例如：账户名和配额等）：

```bash
python kmdr.py status
```

### 4. 回调函数

你可以设置一个回调函数，下载完成后执行。回调可以是任何你想要的命令：

```bash
python kmdr.py download -d path/to/destination --book-url https://kox.moe/c/50076.htm -v 1-3 -c "echo '{b.name} {v.name} downloaded!'"
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

> 完成的可用参数请参考 [structure.py](https://github.com/chrisis58/kmdr/blob/main/core/structure.py) 中的定义。
