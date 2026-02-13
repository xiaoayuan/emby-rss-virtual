# Emby RSS Virtual Libraries

用于 Emby 的“RSS 驱动虚拟库”服务：
- 真实媒体文件在 `MEDIA_ROOT`（只读）
- 支持在 Web 页面动态新增/管理 RSS 来源
- 在 Web 页面配置规则（绑定来源、关键词、上限）
- 在 `VIRTUAL_ROOT` 生成每日更新的软链接目录
- Emby 直接扫 `VIRTUAL_ROOT` 下的各个子目录

## 1. 快速启动

```bash
cd emby-rss-virtual
cp config/rules.yaml config/rules.yaml.bak
# 修改 rules.yaml 的 RSS 和规则

# 修改 docker-compose.yml 里的两个主机路径：
# /path/to/your/real/library:/media:ro
# /path/to/your/virtual/library:/virtual

docker compose up -d --build
```

启动后打开：
- Web: http://你的NASIP:8080
- 健康检查: `/health`

## 2. Emby 里怎么用

在 Emby 新增媒体库，路径指向：
- `/path/to/your/virtual/library/rss-国产剧追更`
- `/path/to/your/virtual/library/rss-奈飞榜单`

这些目录由服务每天重建。

## 3. 配置说明

现在支持两种配置入口：
- Web 页面（推荐）：来源管理 + 规则管理（存到 SQLite）
- `config/rules.yaml`：首次启动用于种子导入

现在推荐在 Web 的“系统设置”里维护密钥与调度。  
`docker-compose.yml` 仅保留容器启动基础项（挂载/端口/时区）。

环境变量（可选兜底）：
- `TMDB_API_KEY`: TMDB 密钥兜底
- `TRAKT_CLIENT_ID`: Trakt 密钥兜底

来源 `kind` 支持：
- `rss`：`rss_url` 填标准 RSS 链接
- `tmdb`：`rss_url` 填参数串，如 `media=tv&region=US&provider=8&limit=30`
- `trakt`：`rss_url` 填参数串，如 `kind=shows&mode=trending&limit=30`
- `justwatch`：`rss_url` 填参数串，如 `country=US&content=show&provider=nfx&limit=30`（best-effort）

## 4. 调度

环境变量 `CRON_EXPR`（默认 `30 3 * * *`）
- 每天 03:30 自动刷新一次
- Web 页面可手动“立即刷新一次”

## 5. Emby 联动（新增）

Web 页面支持填写：
- Emby 地址（如 `http://NAS:8096`）
- Emby API Key
- 刷新后自动通知 Emby 扫描

也可手动点击“立即触发 Emby 扫描”。

## 6. 注意事项

1. 当前匹配策略是“标题与文件名模糊匹配”（v1）。
2. 预设 Netflix/HBO/Disney+/AppleTV 来源是占位示例 URL，请替换为可用 RSS。  
3. 后续可扩展为：
   - 优先读取 `.nfo` 的 `tmdbid/imdbid`
   - 按季/集更精准匹配
   - 支持多用户规则、白名单目录
4. 软链接方案要求 Emby 对该路径有读取权限。
