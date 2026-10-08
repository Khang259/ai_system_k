# AMR Camera Dispatch System — Layered Architecture

Backend FastAPI: camera AI (GPU) + điều phối node/pair + API cho FE (`/api/v1`).

## Yêu cầu thiết bị mới

| Thành phần | Ghi chú |
|------------|---------|
| **OS** | Windows 10/11 (repo dùng `pywin32`, `mediamtx.exe`) |
| **Python** | ≥ 3.10 (xem `.python-version`) |
| **uv** | Package manager — [cài uv](https://docs.astral.sh/uv/getting-started/installation/) |
| **MongoDB** | Chạy local; mặc định `mongodb://127.0.0.1:27018`, DB `db_kortek` |
| **NVIDIA GPU + CUDA** | Pipeline **chỉ GPU** (decode NVDEC + TensorRT) — không có fallback CPU |
| **TensorRT** | Khớp version CUDA; dùng file `.engine` |
| **FFmpeg (NVDEC)** | Bản full có GPU — thêm vào `PATH` |
| **Model** | Đặt file engine tại `models/model_test.engine` (hoặc sửa `MODEL_PATH` trong `.env`) |

## Chạy lần đầu

### 1. Clone & vào thư mục

```powershell
git clone <repo-url>
cd kortek
```

### 2. Cài dependency

```powershell
uv sync
```

Cài PyTorch CUDA (nếu chưa có trong sync):

```powershell
uv pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 --index-url https://download.pytorch.org/whl/cu128
```

### 3. Tạo file `.env`

Copy mẫu dưới đây thành `.env` ở **root repo** (cùng cấp `app.py`). Chỉ sửa những gì khác máy bạn.

```env
# Server
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=5000

# MongoDB
MONGODB_URL=mongodb://127.0.0.1:27018
MONGODB_DB=db_kortek

# Auth — production PHẢI set cố định (trống = secret đổi mỗi lần restart → token cũ mất)
JWT_SECRET=doi-chuoi-bi-mat-dai-va-ngau-nhien

# Model AI
MODEL_PATH=models/model_test.engine

# ICS / AMR (điền URL thật của site)
# ICS_URL=http://192.168.1.4:7000/ics/taskOrder/addTask
```

Các biến khác có default trong `config/settings.py` — chỉ thêm vào `.env` khi cần ghi đè.

### 4. Bật MongoDB

Đảm bảo Mongo lắng nghe đúng port trong `MONGODB_URL` (mặc định **27018**).

### 5. Seed user đăng nhập

Chưa có API đăng ký — tạo 3 tài khoản mặc định (`admin`, `operator`, `viewer`):

```powershell
uv run python scripts/seed_users.py
```

Script hỏi **một mật khẩu chung** (≥ 8 ký tự) cho các user mới tạo.

### 6. (Tuỳ chọn) Seed camera mock

Chỉ khi cần data giả để stress / demo:

```powershell
uv run python scripts/seed_db.py
```

### 7. Chạy API

```powershell
uv run uvicorn app:app --host 0.0.0.0 --port 5000 --reload
```

- Swagger: http://127.0.0.1:5000/docs  
- Login: `POST /api/v1/auth/login` với `username` / `password` vừa seed  

## Kiểm tra nhanh sau khi lên

1. `GET /api/v1/system/get_health` — Mongo / runtime ổn.  
2. Login lấy token → gọi các API có auth.  
3. Inference / camera chỉ chạy khi đã có model `.engine`, GPU OK, và đã cấu hình camera/ROI trong DB.

## Cấu trúc thư mục (tóm tắt)

| Thư mục | Vai trò |
|---------|---------|
| `domain/` | Logic nghiệp vụ thuần (node state, permissions…) |
| `application/` | Use case + ports (FE API, runtime…) |
| `infrastructure/` | Mongo, vision/GPU, auth, WebRTC… |
| `presentation/` | FastAPI routes + schemas |
| `config/` | Settings từ `.env` |
| `scripts/` | Seed DB / user, tiện ích vận hành |
| `models/` | File model TensorRT / ONNX |
| `tests/` | Pytest |
| `docs/` | Tài liệu tích hợp FE / contract API |

## Tài liệu FE

- [Zone runtime flags — `isRunning` / `isStreaming`](docs/fe-zones-runtime-flags.md)

## Ghi chú

- **Không commit** file `.env`, model lớn, hay log.  
- Máy mới thiếu CUDA / TensorRT / FFmpeg GPU → app có thể lên được CRUD, nhưng **không chạy được pipeline detect**.  
- Dev: `JWT_SECRET` trống vẫn chạy được; mỗi restart hết hiệu lực token cũ.
