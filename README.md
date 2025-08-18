# ChalaoshiPy

基于Gunicorn的查老师离线版，使用[查老师](https://github.com/zjuchalaoshi/chalaoshi)的公开静态数据。

## 数据说明

### 手动添加数据

将[查老师](https://github.com/zjuchalaoshi/chalaoshi)的数据解压放在data目录下，如 `data/comment_*.csv`

### 使用py程序加载数据

您需要将获取到的`zip`文件放在与`update_data.py`同目录下，然后运行：

```bash
python update_data.py --update
```

随后根据引导输入：压缩包名，SHA256值（可选，用于校验数据包完整性），CC98用户名和密码（用于登录CC98论坛），主题ID，楼层号，即可自动获取数据。

请确保您能够访问CC98论坛。

主题ID可以通过URL查看，如 https://www.cc98.org/topic/5399305/317#1 中的 `5399305`就是主题ID。程序将会获取相应回复并计算出SHA256值作为解压密码，将数据保存在`data`目录下。

请不要高强度通过这个url访问，这会增加98服务器的负担，还可能会被CC98论坛封禁。

## 启动说明

Gunicorn 不能在 Windows 上运行，请考虑使用 Linux 或 WSL。

请您先设置名为 `SECRET_KEY` 的环境变量，可以使用

```python
import secrets
secrets.token_hex(24)
```

然后运行：

```bash
pip install -r requirements.txt
gunicorn --workers 4 --bind 0.0.0.0:5000 app:app
```

### 计划中的增加内容

- [ ] 数据更新时间
- [x] 自动读取压缩包解压
- [ ] Docker部署