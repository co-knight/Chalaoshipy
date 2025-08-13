# ChalaoshiPy

基于Gunicorn的查老师离线版，使用[查老师](https://github.com/zjuchalaoshi/chalaoshi)的公开静态数据。

## 数据说明

将[查老师](https://github.com/zjuchalaoshi/chalaoshi)的数据放在data目录下，如 `data/comment_*.csv`

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
- [ ] 自动读取压缩包解压
- [ ] Docker部署