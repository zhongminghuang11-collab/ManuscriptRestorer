# Repository maintenance / 仓库维护

Public repository: https://github.com/zhongminghuang11-collab/ManuscriptRestorer

## Release checklist

1. Run `python -m pip install -r requirements.txt`, `python -m unittest discover -s tests -v` and `python verify_demo.py`.
2. Confirm that README's experimental status and `KNOWN_ISSUES.md` accurately describe known defects and unverified claims.
3. Ensure `data/projects/` contains no real manuscript, personal data, or exported user projects. Never commit credentials, model weights, or private images.
4. Review the licenses of added dependencies or datasets before merging.
5. Submit changes through a pull request; let repository checks complete and review failures before merging.
6. For releases, add a clear changelog, mark unresolved issues, and avoid claims of handwriting accuracy without held-out benchmarks.

## Local contributions

```bash
git clone https://github.com/zhongminghuang11-collab/ManuscriptRestorer.git
cd ManuscriptRestorer
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python verify_demo.py
```

This project is distributed under MIT. External OCR engines, optional vision models, sample data, and any dependencies retain their own licenses. Anyone may fork and change the code, while changes to the upstream repository are reviewed through pull requests.
