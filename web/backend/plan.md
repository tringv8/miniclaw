# Plan: Viết lại Go backend thành Python (FastAPI) cho web/

## Context
Viết lại go backend thành Python (FastAPI)  vào trong thư mục web\frontend_python_codex
Thư mục `web/` chứa giao diện quản lý (frontend Vite+React + backend Go) lấy từ dự án Miniclaw Web.
Backend Go vẫn bám import path legacy nên không tương thích với miniclaw.
Vì toàn bộ dự án là Python, cần viết lại backend bằng **FastAPI** để:
- Không cần cài Go toolchain
- Đọc/ghi đúng config format của miniclaw (`~/.miniclaw/config.json`)
- Gọi đúng miniclaw gateway (port 18790)
- Giữ nguyên frontend (chỉ thay đổi API base URL nếu cần)

## Danh sách endpoints cần implement (từ Go backend)

### Auth (cookie-based session)
- `POST /api/auth/login` - đăng nhập bằng dashboard token
- `POST /api/auth/logout` - xóa cookie session
- `GET /api/auth/status` - kiểm tra trạng thái đăng nhập

### Config
- `GET /api/config` - đọc config.json của miniclaw
- `PUT /api/config` - ghi đè toàn bộ config
- `PATCH /api/config` - cập nhật một phần config

### Gateway
- `GET /api/gateway/status` - kiểm tra miniclaw gateway có đang chạy không
- `GET /api/gateway/logs` - lấy log gateway
- `POST /api/gateway/logs/clear` - xóa log
- `POST /api/gateway/start` - khởi động `miniclaw gateway`
- `POST /api/gateway/stop` - dừng gateway
- `POST /api/gateway/restart` - restart gateway

### Models
- `GET /api/models` - danh sách model trong config
- `POST /api/models` - thêm model
- `POST /api/models/default` - đặt model mặc định
- `PUT /api/models/{index}` - sửa model theo index
- `DELETE /api/models/{index}` - xóa model

### Sessions
- `GET /api/sessions` - danh sách session
- `GET /api/sessions/{id}` - lấy 1 session
- `DELETE /api/sessions/{id}` - xóa session

### Channels
- `GET /api/channels/catalog` - danh sách channels có trong miniclaw

### OAuth
- `GET /api/oauth/providers` - danh sách OAuth providers (gemini, openai-codex...)
- `POST /api/oauth/login` - bắt đầu OAuth flow
- `GET /api/oauth/flows/{id}` - trạng thái OAuth flow
- `POST /api/oauth/flows/{id}/poll` - poll OAuth flow
- `POST /api/oauth/logout` - logout OAuth provider
- `GET /oauth/callback` - OAuth callback

### Skills
- `GET /api/skills` - danh sách skills trong workspace
- `GET /api/skills/{name}` - lấy skill
- `POST /api/skills/import` - import skill
- `DELETE /api/skills/{name}` - xóa skill

### Tools
- `GET /api/tools` - danh sách tools
- `PUT /api/tools/{name}/state` - bật/tắt tool

### System
- `GET /api/system/autostart` - có autostart không
- `PUT /api/system/autostart` - bật/tắt autostart
- `GET /api/system/launcher-config` - cấu hình launcher (port, public)
- `PUT /api/system/launcher-config` - cập nhật launcher config

### Pico WebSocket (chat)
- `GET /api/mini/token` - lấy token kết nối WebSocket
- `POST /api/mini/token` - tái tạo token
- `POST /api/mini/setup` - setup web channel
- `GET /mini/ws` - WebSocket proxy đến miniclaw gateway

### Bỏ qua (không liên quan miniclaw)
- WeChat (`/api/weixin/...`) - chỉ có trong launcher cũ
- WeCom (`/api/wecom/...`) - chỉ có trong launcher cũ

## Cấu trúc file mới

**Nguyên tắc**: Giữ nguyên cấu trúc thư mục Go, thêm file `.py` tương ứng từng file `.go`.
Các file `.go` giữ lại làm tài liệu tham khảo, KHÔNG xóa.

```
web/backend/
  main.py                          # ← MỚI: thay main.go, entry point uvicorn
  app_runtime.py                   # ← MỚI: thay app_runtime.go, quản lý process
  i18n.py                          # ← MỚI: thay i18n.go (nếu cần)
  requirements.txt                 # ← MỚI: thay go.mod
  main.go                          # GIỮ (tham khảo)
  app_runtime.go                   # GIỮ (tham khảo)
  ...các .go khác                  # GIỮ (tham khảo)
  dist/                            # GIỮ NGUYÊN (frontend build output)
  winres/                          # GIỮ NGUYÊN (không liên quan Python)
  api/
    __init__.py                    # ← MỚI
    router.py                      # ← MỚI: thay router.go, đăng ký tất cả routes
    auth.py                        # ← MỚI: thay auth.go + auth_login_limiter.go
    config.py                      # ← MỚI: thay config.go
    gateway.py                     # ← MỚI: thay gateway.go + gateway_host.go
    launcher_config.py             # ← MỚI: thay launcher_config.go
    log.py                         # ← MỚI: thay log.go
    model_status.py                # ← MỚI: thay model_status.go
    models.py                      # ← MỚI: thay models.go
    oauth.py                       # ← MỚI: thay oauth.go
    mini.py                        # ← MỚI: thay websocket handler cũ
    session.py                     # ← MỚI: thay session.go
    skills.py                      # ← MỚI: thay skills.go
    startup.py                     # ← MỚI: thay startup.go
    tools.py                       # ← MỚI: thay tools.go
    channels.py                    # ← MỚI: thay channels.go
    # wecom.py / weixin.py BỎ QUA (chỉ có trong launcher cũ)
    *.go                           # GIỮ (tham khảo)
  middleware/
    __init__.py                    # ← MỚI
    middleware.py                  # ← MỚI: thay middleware.go, setup FastAPI middleware
    access_control.py              # ← MỚI: thay access_control.go
    launcher_dashboard_auth.py     # ← MỚI: thay launcher_dashboard_auth.go
    referrer_policy.py             # ← MỚI: thay referrer_policy.go
    *.go                           # GIỮ (tham khảo)
  model/
    __init__.py                    # ← MỚI
    status.py                      # ← MỚI: thay status.go, Pydantic models
    *.go                           # GIỮ (tham khảo)
  launcherconfig/
    __init__.py                    # ← MỚI
    config.py                      # ← MỚI: thay config.go, đọc/ghi launcher config
    *.go                           # GIỮ (tham khảo)
  utils/
    __init__.py                    # ← MỚI
    banner.py                      # ← MỚI: thay banner.go
    onboard.py                     # ← MỚI: thay onboard.go
    runtime.py                     # ← MỚI: thay runtime.go
    *.go                           # GIỮ (tham khảo)
```

## Các điểm tích hợp với miniclaw

| Chức năng | Cách implement |
|-----------|----------------|
| Config | Dùng `miniclaw.config.loader.load_config/save_config` |
| Sessions | Đọc file từ `~/.miniclaw/sessions/` |
| Skills | Đọc thư mục `workspace/skills/` |
| Gateway start/stop | `subprocess.Popen(["miniclaw", "gateway"])` |
| OAuth | Dùng `oauth_cli_kit` có sẵn trong project |
| Channels | Dùng `miniclaw.channels.registry.discover_all()` |

## Verification

1. `cd web && pip install -r requirements.txt`
2. `uvicorn web.backend.main:app --port 18800`
3. Mở browser `http://localhost:18800`
4. Test đăng nhập, xem config, start/stop gateway
