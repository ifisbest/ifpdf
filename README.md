# ifpdf

> 让几百页的扫描版学术专著变成 AI 能精确引用到页码的结构化 Markdown。

---

## 问题：为什么现有工具不够好？

人文社科研究者从 Anna's Archive、图书馆数据库获取的 PDF 大多是**扫描版（纯图片）**。当你把书丢给 Claude / ChatGPT / Cursor 时——

```
AI: "抱歉，我无法读取这个 PDF 的内容。"
```

现有工具的局限：

| 工具 | 核心缺陷 |
|------|---------|
| **Adobe Acrobat Pro** | 订阅制；无 CLI 无法批量；导出格式混乱，页码丢失 |
| **ABBYY FineReader** | 价格高昂；无 CLI；输出不友好 |
| **Tesseract CLI** | 无 PDF 管道；需手动拆页调参；无页码无结构 |
| **Marker / Nougat** | 2GB+ 模型；针对英文论文；不处理扫描版 |
| **在线 OCR 服务** | 隐私风险；无法自动化；中文识别差 |

**市场上没有一款工具**同时满足：扫描版中文 PDF OCR + 保留精确页码 + CLI 批量自动化 + 输出 AI 友好格式。

---

## 方案：ifpdf

```bash
ifpdf ocr book.pdf --content-starts-at 25 --chunk-size 4000
```

**转换前**（直接上传 PDF）：
```
AI: "抱歉，我无法读取这个 PDF 的内容。"
```

**转换后**（上传 Markdown）：
```
研究者："请总结刘勇强对《红楼梦》叙事结构的分析"

AI: "根据刘勇强《中国古代小说史叙论》（北京大学出版社 2007）
     第 234-238 页 的论述，作者从三个层面分析了《红楼梦》的叙事结构..."
```

---

## 核心特性

### 1. 智能 OCR 管道
- **自动检测**扫描版 vs 文字层 PDF，无需用户判断
- **多进程并行**（`--workers 4`），600 页书从 50 分钟 → 12-15 分钟
- **图像预处理**：二值化、降噪、对比度增强
- **双引擎**：Tesseract（默认，离线）/ PaddleOCR（可选，中文更快）

### 2. 页码对齐系统
扫描版 PDF 的物理页 ≠ 正文页码（封面、版权页、前言 = 前 N 页）。

```bash
ifpdf ocr book.pdf --content-starts-at 25
# PDF 第 25 页 = 正文第 1 页
```

输出格式：
```markdown
<!-- 第 1 页 -->
第一章 导论

中国古代小说的发展历程源远流长...

<!-- 第 2 页 -->
对于"小说"这一概念，历代学者的理解并不一致...
```

### 3. 元数据自动提取
从 Anna's Archive 风格文件名自动解析：
```
中国古代小说史叙论-_刘勇强著_2007_--_北京市：北京大学出版社_--_9787301122303
```
提取：书名、作者、出版年、出版社、ISBN。

缺失字段支持**交互式补全**（`--interactive`）。

### 4. 智能分块
LLM 有上下文限制，一本 30 万字的书无法一次性塞入：

```bash
ifpdf ocr book.pdf --chunk-size 4000
```

```markdown
<!-- === CHUNK 1/15（第 1-45 页）=== -->
[内容]

<!-- === CHUNK 2/15（第 46-91 页）=== -->
[内容]
```

每块带页码范围，AI 回答时可以精确定位引用来源。

### 5. 批量处理
```bash
# 批量转一个文件夹
ifpdf batch ./books/ -o ./output/

# 多进程并行处理多个文件
ifpdf batch ./books/ --workers 4
```

---

## 安装

```bash
# 克隆仓库
git clone https://github.com/ifisbest/ifpdf.git
cd ifpdf

# 创建虚拟环境并安装
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# OCR 支持（需要系统安装 Tesseract）
pip install "ifpdf[ocr]"
```

**系统依赖**：
```bash
# macOS
brew install tesseract tesseract-lang

# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-chi-sim
```

---

## 使用

### 单文件 OCR
```bash
# 基础转换（自动检测扫描版/文字层）
ifpdf ocr book.pdf -o book.md

# 指定正文起始页码
ifpdf ocr book.pdf --content-starts-at 25 -o book.md

# 交互式补全元数据
ifpdf ocr book.pdf --interactive -o book.md

# 4 进程并行 OCR + 4000 token 分块
ifpdf ocr book.pdf --workers 4 --chunk-size 4000 -o book.md

# 仅处理前 50 页
ifpdf ocr book.pdf --pages 1-50 -o book.md
```

### 批量处理
```bash
ifpdf batch ./books/ -o ./output/ --workers 4
```

### 已有 Markdown 分块
```bash
ifpdf chunk book.md --chunk-size 4000 -o ./chunks/
```

### 查看 PDF 信息
```bash
ifpdf info book.pdf
```

---

## 技术架构

```
PDF 输入
  ↓
[检测] 有文字层？→ 是：直接提取（PyMuPDF + pdfplumber）
              → 否：OCR 流程
  ↓
[渲染] pdf2image → 高分辨率 PNG (300 DPI)
  ↓
[预处理] Pillow：二值化、降噪、对比度增强
  ↓
[识别] Tesseract (chi_sim) / PaddleOCR (可选)
  ↓
[布局分析] 字体大小/粗细检测 → heading / body / table 分类
  ↓
[格式化] Markdown 输出（含页码映射、元数据头）
  ↓
[分块] tiktoken 感知分块（段落边界 → 句子边界 → 字符边界）
  ↓
Markdown 输出
```

```
ifpdf/
├── cli.py              # Typer CLI（ocr, batch, chunk, info）
├── extractor.py        # 文字层 PDF 提取（PyMuPDF）
├── ocr_engine.py       # OCR 引擎封装（Tesseract / PaddleOCR）
├── preprocessor.py     # 图像预处理
├── layout.py           # 布局分析（标题/正文/页眉页脚识别）
├── formatter.py        # Markdown 格式化输出
├── chunker.py          # Token 感知分块（tiktoken）
├── metadata.py         # 文件名解析 + 交互式补全
├── pagemap.py          # 页码映射（PDF页 → 正文页）
└── utils.py            # 文件操作、剪贴板、进度显示
```

---

## 性能指标

| 场景 | 配置 | 时间 |
|------|------|------|
| 30 页论文（扫描版） | 单进程 Tesseract | 2-3 分钟 |
| 30 页论文（扫描版） | 4 进程 Tesseract | 1 分钟 |
| 600 页专著（扫描版） | 单进程 Tesseract | 50-60 分钟 |
| 600 页专著（扫描版） | 4 进程 Tesseract | 12-15 分钟 |
| 600 页专著（扫描版） | PaddleOCR 单进程 | 20-25 分钟 |
| 有文字层 PDF | 直接提取 | 秒级 |

---

## 与 AI 工作流的配合

```
[扫描版 PDF 书籍]
        ↓
   ifpdf ocr --content-starts-at 25 --chunk-size 4000
        ↓
[结构化 Markdown (.md)]
        ↓
放入 ~/文献库/
        ↓
Claude Code / Cursor 读取
        ↓
AI 问答 + 精确到页码的引用
```

---

## 测试

```bash
pytest tests/ -v
```

34 个测试覆盖：分块、布局分析、元数据解析、页码映射、图像预处理。

---

## License

MIT
