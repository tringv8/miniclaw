---
name: arxiv-watcher
description: Search and summarize papers from ArXiv. Use when the user asks for the latest research, specific topics on ArXiv, or a daily summary of AI papers.
---

# ArXiv Watcher

Skill này kết nối ArXiv API để tìm các bài báo khoa học theo từ khoá hoặc ID.

## Workflow

### Bước 1 — Chạy script tìm kiếm

```bash
python scripts/search_arxiv.py "<query>" [max_results]
```

Ví dụ:
```bash
python scripts/search_arxiv.py "LLM reasoning" 5
python scripts/search_arxiv.py "2512.08769"
```

Script trả về cho mỗi bài:
- `Tiêu đề`
- `Tác giả` (tối đa 4 người)
- `Ngày đăng`
- `Link` (trang abstract trên arxiv.org)
- `DOI` (nếu có)
- `Abstract` (đầy đủ)

### Bước 2 — Trình bày kết quả bằng tiếng Việt

Với **mỗi bài tìm được**, trình bày theo đúng mẫu sau:

---

**[STT]. [Tiêu đề bài báo]**
- 👤 **Tác giả**: [danh sách tác giả]
- 📅 **Ngày đăng**: [YYYY-MM-DD]
- 🔗 **Link**: [link arxiv]
- 📌 **DOI**: [doi nếu có, bỏ qua nếu không có]
- 📝 **Tóm tắt**: [Tóm tắt abstract bằng tiếng Việt, 3–5 câu, súc tích, nêu rõ: bài làm gì, vấn đề giải quyết là gì, kết quả/đóng góp chính là gì]

---

> ⚠️ **Quan trọng**: Phần tóm tắt PHẢI viết bằng **tiếng Việt**, không dịch nguyên văn abstract, hãy diễn đạt lại ngắn gọn và dễ hiểu.

### Bước 3 — Lưu vào memory (bắt buộc)

Sau khi trình bày, append vào `memory/RESEARCH_LOG.md`:

```markdown
### [YYYY-MM-DD] TIÊU ĐỀ BÀI BÁO
- **Tác giả**: ...
- **Link**: ...
- **DOI**: ... (nếu có)
- **Tóm tắt (VI)**: [bản tóm tắt tiếng Việt đã dùng ở Bước 2]
```

## Tham số script

| Tham số | Mô tả | Mặc định |
|---------|-------|---------|
| `query` | Từ khoá hoặc ArXiv ID | *(bắt buộc)* |
| `max_results` | Số lượng kết quả tối đa | `5` |

> Script không cần thư viện ngoài — chỉ dùng Python built-in.
