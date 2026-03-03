# templates/

이 폴더는 당근 광고 기획 도우미 문서 생성에 사용하는 레이아웃 참조 파일을 보관합니다.

## 현재 상태

문서 레이아웃은 `app/reporting/docx_report.py` 에 코드로 완전 구현되어 있으며,
`app/reporting/document_spec.md` 에 설계 명세가 기록되어 있습니다.

물리적 템플릿 파일(.docx)은 향후 v3.0 이상에서 python-docx `Document(template_path)` 방식으로
적용할 예정입니다. 준비되면 이 폴더에 아래 파일을 추가하세요:

```
templates/
├── 성과보고서_template_v1.docx   ← 성과 보고서 기준 레이아웃
└── 기획서_template_v1.docx       ← 광고 기획서 기준 레이아웃
```

## python-docx 템플릿 파일 적용 방법

```python
from docx import Document
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent / "templates"

# 템플릿 로드 (스타일·여백 등 기본값 상속)
doc = Document(TEMPLATE_DIR / "성과보고서_template_v1.docx")
# ... 이후 내용 추가
```

> **주의**: python-docx 템플릿을 사용하면 기존 내용이 초기화되지 않습니다.
> 템플릿에 콘텐츠 컨트롤(content control)이나 플레이스홀더를 사용하려면
> `python-docx-template` 라이브러리(Jinja2 기반)를 권장합니다.
