# ManuscriptRestorer

> **Status: experimental / not ready for unattended transcription.**
>
> This project provides a local workflow for transcribing manuscript images, recording corrections, and reconstructing an original draft and a revised draft. **The recognition of handwritten revisions is not reliable enough for production use.** Review the original image before accepting any OCR text or edit proposal.

[简体中文说明](#中文说明) · [Known issues](KNOWN_ISSUES.md) · [Contributing](CONTRIBUTING.md) · [License](LICENSE) · [Technical notes](TECHNICAL_SPEC.md)

## English summary

Experimental, local-first transcription and edit-tracking toolkit for annotated Chinese manuscripts. It imports images/PDFs, provides OCR-assisted text boxes, records reviewed edits, and exports original/revised text. **Automatic interpretation of handwritten revisions is not reliable or benchmarked on real handwriting.** See [Known issues](KNOWN_ISSUES.md) before use. Contributions via forks and pull requests are welcome under [MIT License](LICENSE).

## 中文说明

ManuscriptRestorer 是一套实验性的中文手稿校勘工具，面向带划除、插入、替换等修改标记的纸质手稿。项目将 OCR 转写结果与修改事件分开存储，允许对每项改动进行人工审核，并导出原稿、终稿与修改记录。

**当前项目更适合作为辅助标注与版本重建工具，而不是全自动手写稿还原工具。**

### 功能

- 导入图片或 PDF，多页查看及文字框标注。
- 使用 Tesseract OCR 识别文字；PaddleOCR 3.x 为可选适配器。
- 检测部分红色横向划除线，生成待审核候选。
- 可选连接本地 Ollama 视觉模型提出修改建议（未经充分实测）。
- 记录删除、替换、前插、后插及字符级修改范围；检测冲突修改。
- 重建原始稿、已确认修改的终稿，保存本地项目并导出 TXT / JSON。
- 提供自动化单元测试及合成示例。

### 安装和运行

需要 Python 3.11+。Windows 用户可运行 `install_windows.bat`，然后运行 `run_windows.bat`。其他平台：

```bash
python -m pip install -r requirements.txt
python server.py
```

浏览器打开 `http://127.0.0.1:8765`。

执行 OCR 时，还需安装 [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html) 和 `chi_sim` 中文语言包。仅使用人工标注、示例重建功能则不需要安装 OCR 主程序。使用前请阅读 [已知缺陷](KNOWN_ISSUES.md)。

可选本地视觉模型：安装 [Ollama](https://ollama.com/) 后自行下载兼容的视觉模型，例如 `qwen3-vl:4b`。视觉模型的输出必须人工审核，且依赖更高的硬件配置。

### 使用方式

1. 上传手稿图像或 PDF；先执行 OCR，再校对文字框。
2. 添加修改事件，或检查红线检测 / 本地视觉模型给出的待审建议。
3. 逐项确认或拒绝修改，检查原稿与终稿。
4. 导出 TXT、审阅记录或项目 JSON。

**请勿直接把自动生成的 OCR 文字、修改建议作为可靠档案。**

### 命令行

```bash
python cli.py analyze fixtures/demo.png --engine tesseract -o project.json
python cli.py render project.json -d export
python verify_demo.py
python -m unittest discover -s tests -v
```

`analyze` 不会自动确认修改。导出终稿之前需要完成校对，并使用保存后的项目文件。

### 当前测试范围

2026-11-22 在开发环境中运行项目自动化测试并通过，另已验证合成样例的确定性修改重建。**这些结果不能证明真实手写稿识别准确。** Tesseract 在合成示例上仍出现了识别错误；尚无大规模真实手稿对照评测。PaddleOCR 与本地视觉模型的完整端到端运行尚未验收，Windows 和不同操作系统的兼容性亦未系统测试。

### 文件结构

| 文件 | 作用 |
|---|---|
| `core.py` | 编辑事件冲突检查与双版本重建 |
| `analyzer.py` | 图片/PDF处理、OCR、红色划线候选检测 |
| `ocr_adapter.py` | PaddleOCR 3.x 适配 |
| `vision_adapter.py` | 本地视觉模型候选分析 |
| `server.py` | 本地 HTTP 服务及项目管理 |
| `web/` | 浏览器校勘界面 |
| `cli.py` | 批处理与导出 |
| `evaluate.py` | 与人工标准答案比较的评估工具 |
| `fixtures/` | 合成测试数据，非真实手写基准 |
| `tests/` | 自动化测试 |

### 开源与贡献

项目源代码依据 [MIT 许可证](LICENSE)开放使用、修改与分发。欢迎通过 **Fork + Pull Request** 提交修复、测试数据处理工具与改进，详见 [贡献指南](CONTRIBUTING.md)。普通用户没有主分支直接写入权限，合并仍需维护者审核。

代码并未打包第三方模型权重。Tesseract、PaddleOCR、Ollama及各模型遵循其各自的许可证。PDF 渲染使用采用 Apache-2.0 / BSD-3-Clause 许可的 `pypdfium2`。**MIT 仅覆盖本项目有权许可的源代码和文档，不改变第三方依赖或数据的授权方式。**

### 研究方向

优先建立真实中文手稿标准数据，分别测量原文 OCR 的字符错误率、编辑操作识别的精确率/召回率、终稿字符错误率以及人工核对时间；在证明确有改善前，不将该系统宣传为自动还原方案。详见 [技术规格](TECHNICAL_SPEC.md) 和 [已知缺陷](KNOWN_ISSUES.md)。
