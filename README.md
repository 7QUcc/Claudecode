# 小克的家

在 iPhone 上接着和 Claude Code 聊天、看终端，界面照着 Claude App 做。

它基于开源项目 [Prism](https://github.com/lumen-prism/prism-oss)（AGPL-3.0）：后端还是 Prism 的，负责用 tmux 接上服务器里正在跑的 `claude`，解析对话记录。在这个基础上我们做了四件事：

- **Claude 暖白主题**：米白纸面、赭橙强调色、回复用衬线字体，还有深色模式。思考过程和工具调用都做成 Claude App 那样的一行摘要，点开从底部弹出详情面板（Command / Output）。页面切换有过渡动画。原来的「素描稿纸」主题还能在设置里切回去。
- **PWA**：可以添加到 iPhone 主屏幕，全屏打开；回到前台时自动重连，漏掉的消息会补上。
- **推送通知**：Claude 做完一轮、或者停下来等你确认时，推送到锁屏。需要 iOS 16.4 以上，并且是从主屏幕打开的 App。
- **适合放在 Cloudflare Tunnel 后面**：默认只监听本机；登录令牌 30 天不用自动过期；按真实 IP 限制密码尝试次数。

---

## 部署到 Ubuntu 服务器

### 1. 装好 Claude Code

服务器上需要有 Node.js，并且登录过一次 Claude Code：

```bash
npm install -g @anthropic-ai/claude-code
claude   # 第一次运行会让你登录
```

### 2. 安装小克的家

```bash
git clone <这个仓库的地址> ~/xiaoke
cd ~/xiaoke
bash deploy/install.sh
```

脚本会做这几件事：
- 装 `python3-venv` 和 `tmux`
- 建一个虚拟环境，装好依赖
- 第一次运行时让你设一个访问密码，写进 `.env`（只有你自己能读）
- 注册一个叫 `xiaoke` 的 systemd 服务，开机自启，崩了会自动重启

装好以后，它在 `http://127.0.0.1:8001` 运行，**只有本机能访问**。

以后更新代码也用同一个脚本：先 `git pull`，再跑一遍 `bash deploy/install.sh`。重启服务不会杀掉正在跑的 Claude 会话。

常用命令：

```bash
sudo systemctl status xiaoke        # 看状态
sudo journalctl -u xiaoke -f        # 看日志
sudo systemctl restart xiaoke       # 重启
```

### 3. 接到 Cloudflare Tunnel

你已经有一条 tunnel 了，只需要给它**加一个子域名**，不用新建 tunnel。

**如果 tunnel 是在 Cloudflare 网页后台管理的：**
1. 打开 Cloudflare 控制台，进入 Zero Trust → Networks → Tunnels，选你的 tunnel，点 Edit
2. 切到 Public Hostname 标签，点 Add a public hostname
3. Subdomain 填比如 `home`，Domain 选你的域名；Service 选 `HTTP`，URL 填 `localhost:8001`
4. 保存

**如果 tunnel 用的是本地配置文件**（`~/.cloudflared/config.yml` 或 `/etc/cloudflared/config.yml`）：参照 `deploy/cloudflared-ingress.yml`，把那条规则加到最后那条 `http_status:404` 前面，然后运行 `sudo systemctl restart cloudflared`。

### 4. 加一层 Cloudflare Access（强烈建议）

加了以后，陌生人连登录页都看不到。

1. 打开 Zero Trust → Access → Applications → Add an application，选 Self-hosted
2. Application domain 填上一步的子域名，比如 `home.你的域名`
3. Session Duration 选 `1 month`，这样手机不会天天让你重新验证
4. 加一条 Policy：Action 选 Allow，Include 选 Emails，填你自己的邮箱
5. 保存

以后第一次打开时，Cloudflare 会给你的邮箱发一个验证码，输入后才能看到小克的家的登录页。小克的家自己的密码是第二道锁。

> 推送通知是苹果的服务器直接发到手机的，不经过 Access，所以不受影响。

### 5. 装到 iPhone 主屏幕

1. 用 **Safari** 打开 `https://home.你的域名`
2. 点底部的分享按钮 → 添加到主屏幕，名字就叫「小克的家」→ 添加
3. 从主屏幕图标打开，输入密码登录。主屏幕 App 和 Safari 的登录是分开的，所以要再登一次
4. 进入 设置 → 通知，打开推送通知，iPhone 会问你是否允许，点允许
5. 点「发一条测试通知」，锁屏收到了就说明通了 🎉

---

## 推送什么时候会响

后台每隔几秒看一次每个 Claude Code / Codex 会话：

| 情况 | 通知 |
|---|---|
| 一轮做完了（正在干活 → 停下来） | 「xxx 做完了」，内容是它最后说的话 |
| 停在权限确认、选择题、提问卡片上 | 「xxx 在等你」，内容是它在问什么 |

- 你正在手机上看某个会话时，这个会话不会推送。
- 两种通知可以在设置里分别开关。
- 想整个关掉推送，在 `.env` 里加一行 `PUSH_DISABLED=1`。

## 配置项（`.env`）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DASHBOARD_PASSWORD` | 无，必填 | 登录密码 |
| `PORT` | `8001` | 端口 |
| `HOST` | `127.0.0.1` | 监听地址。想让局域网访问才改成 `0.0.0.0` |
| `TOKEN_TTL_DAYS` | `30` | 一台设备多少天不用就要重新登录 |
| `PUSH_CONTACT` | `mailto:xiaoke@localhost` | 推送签名里的联系方式，建议填你的邮箱 |
| `PUSH_DISABLED` | 空 | 设成 `1` 就关掉推送 |
| `PRISM_DATA_DIR` | `~/.local/share/prism` | 聊天索引、推送密钥和订阅存放的位置 |

Telegram 频道等其他功能跟原版一样，说明见 [docs/PRISM_UPSTREAM.md](docs/PRISM_UPSTREAM.md)。

## 许可

基于 Prism，沿用 [AGPL-3.0](LICENSE)。自己用随便改；如果把改过的版本提供给别人用，需要同样开源。
