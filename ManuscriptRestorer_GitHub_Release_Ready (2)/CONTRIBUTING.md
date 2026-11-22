# Contributing / 参与贡献

ManuscriptRestorer 是一个实验性项目，欢迎提交 bug 报告、改进思路、文档更新与代码贡献。

## 如何参与

1. 先浏览 [Known issues](KNOWN_ISSUES.md) 和现有 GitHub Issues，避免重复工作。
2. 通过 GitHub **Fork** 建立个人副本，创建独立开发分支。
3. 修改代码并增补相应的自动化测试；重要算法调整请说明测试样本与失败案例。
4. 在本地运行：

   ```bash
   python -m pip install -r requirements.txt
   python -m unittest discover -s tests -v
   python verify_demo.py
   ```

5. 发起 Pull Request (PR)，说明变更、复现步骤、测试结果和兼容性影响。维护者审核后决定是否合并。

**所有人都可以根据 MIT 许可证复制、修改和分发本仓库，但普通贡献者不能直接写入主分支；请通过 Fork + Pull Request 协作。**

## 最需要帮助的方向

- 真实中文手写稿识别的可复现评测（需要使用得到授权且脱敏的数据）。
- 复杂删除线、插入符号、边注与修改锚点识别。
- OCR 适配器的版本兼容性和统一接口。
- Unicode 字符偏移、竖排版面与跨页修改。
- Windows/macOS/Linux 安装体验、自动化测试和无障碍交互。

## 提交标准

- 不要把未经验证的模型输出视作正确答案，不要将仅通过单元测试描述为手写识别准确。
- 修复错误时尽量增加一个可重复的回归测试。
- 不上传未经许可的手稿、私人图像或包含姓名地址的日志。
- 不上传 access tokens、API 密钥、私有模型数据或其他秘密。
- 大型依赖、新模型权重或许可证变更请先开 Issue 讨论。
- 小改动无需 Issue；与维护者沟通时保持技术讨论和相互尊重。

## 授权

项目源代码采用 [MIT License](LICENSE)。贡献者提交 PR，即表示其有权按项目许可证提供自己提交的内容；第三方数据、预训练模型及依赖遵循各自许可证。
