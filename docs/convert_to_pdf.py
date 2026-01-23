#!/usr/bin/env python3
"""
Markdown을 PDF로 변환하기 위한 HTML 생성 스크립트
생성된 HTML을 브라우저에서 열고 "PDF로 저장"을 사용하세요.
"""

import re

def markdown_to_html(md_content):
    """간단한 Markdown to HTML 변환"""
    html = md_content
    
    # 코드 블록 처리 (```로 둘러싸인 부분)
    html = re.sub(r'```([^`]+?)```', r'<pre><code>\1</code></pre>', html, flags=re.DOTALL)
    
    # 제목 처리
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^##### (.+)$', r'<h5>\1</h5>', html, flags=re.MULTILINE)
    
    # 굵은 글씨
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    # 기울임
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    
    # 인라인 코드
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
    
    # 표 처리 (간단한 버전)
    lines = html.split('\n')
    result_lines = []
    in_table = False
    table_buffer = []
    
    for i, line in enumerate(lines):
        if '|' in line and not line.strip().startswith('<'):
            if not in_table:
                in_table = True
                table_buffer = ['<table>']
            
            # 구분선 행 건너뛰기
            if re.match(r'^\|[\s\-:]+\|', line):
                continue
            
            # 테이블 행 처리
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            
            # 첫 행은 헤더
            if len(table_buffer) == 1:
                table_buffer.append('<thead><tr>')
                for cell in cells:
                    table_buffer.append(f'<th>{cell}</th>')
                table_buffer.append('</tr></thead><tbody>')
            else:
                table_buffer.append('<tr>')
                for cell in cells:
                    table_buffer.append(f'<td>{cell}</td>')
                table_buffer.append('</tr>')
        else:
            if in_table:
                table_buffer.append('</tbody></table>')
                result_lines.extend(table_buffer)
                table_buffer = []
                in_table = False
            result_lines.append(line)
    
    if in_table:
        table_buffer.append('</tbody></table>')
        result_lines.extend(table_buffer)
    
    html = '\n'.join(result_lines)
    
    # 리스트 처리
    lines = html.split('\n')
    result_lines = []
    in_list = False
    
    for line in lines:
        if re.match(r'^- ', line):
            if not in_list:
                result_lines.append('<ul>')
                in_list = True
            content = re.sub(r'^- ', '', line)
            result_lines.append(f'<li>{content}</li>')
        elif re.match(r'^\d+\. ', line):
            if not in_list:
                result_lines.append('<ol>')
                in_list = True
            content = re.sub(r'^\d+\. ', '', line)
            result_lines.append(f'<li>{content}</li>')
        else:
            if in_list:
                # ul인지 ol인지 확인
                if result_lines and '<ul>' in '\n'.join(result_lines[-10:]):
                    result_lines.append('</ul>')
                else:
                    result_lines.append('</ol>')
                in_list = False
            result_lines.append(line)
    
    if in_list:
        if '<ul>' in '\n'.join(result_lines[-10:]):
            result_lines.append('</ul>')
        else:
            result_lines.append('</ol>')
    
    html = '\n'.join(result_lines)
    
    # 단락 처리
    html = re.sub(r'\n\n', '</p><p>', html)
    html = '<p>' + html + '</p>'
    
    # 빈 단락 제거
    html = re.sub(r'<p>\s*</p>', '', html)
    
    # 제목, 표, 리스트 태그 안의 <p> 제거
    html = re.sub(r'<(h[1-6]|table|ul|ol|li|thead|tbody|tr|th|td)><p>', r'<\1>', html)
    html = re.sub(r'</p></(h[1-6]|table|ul|ol|li|thead|tbody|tr|th|td)>', r'</\1>', html)
    html = re.sub(r'<p>(<h[1-6]>)', r'\1', html)
    html = re.sub(r'(</h[1-6]>)</p>', r'\1', html)
    html = re.sub(r'<p>(<table>)', r'\1', html)
    html = re.sub(r'(</table>)</p>', r'\1', html)
    html = re.sub(r'<p>(<ul>|<ol>)', r'\1', html)
    html = re.sub(r'(</ul>|</ol>)</p>', r'\1', html)
    
    # 수평선
    html = re.sub(r'^---$', '<hr>', html, flags=re.MULTILINE)
    
    return html


def create_html_with_style(content):
    """HTML 템플릿 생성"""
    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>수능 점수 변환 및 추정 방법 안내</title>
    <style>
        @page {{
            size: A4;
            margin: 20mm;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Noto Sans KR', 'Malgun Gothic', '맑은 고딕', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 210mm;
            margin: 0 auto;
            padding: 20px;
            background: white;
        }}
        
        h1 {{
            color: #1a1a1a;
            font-size: 28px;
            font-weight: 700;
            margin: 30px 0 20px 0;
            padding-bottom: 10px;
            border-bottom: 3px solid #0066cc;
            page-break-after: avoid;
        }}
        
        h2 {{
            color: #0066cc;
            font-size: 22px;
            font-weight: 700;
            margin: 25px 0 15px 0;
            padding-left: 10px;
            border-left: 4px solid #0066cc;
            page-break-after: avoid;
        }}
        
        h3 {{
            color: #0066cc;
            font-size: 18px;
            font-weight: 600;
            margin: 20px 0 12px 0;
            page-break-after: avoid;
        }}
        
        h4 {{
            color: #333;
            font-size: 16px;
            font-weight: 600;
            margin: 15px 0 10px 0;
            page-break-after: avoid;
        }}
        
        h5 {{
            color: #555;
            font-size: 14px;
            font-weight: 600;
            margin: 12px 0 8px 0;
            page-break-after: avoid;
        }}
        
        p {{
            margin: 10px 0;
            text-align: justify;
        }}
        
        ul, ol {{
            margin: 10px 0;
            padding-left: 30px;
        }}
        
        li {{
            margin: 5px 0;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            page-break-inside: avoid;
            background: white;
        }}
        
        th {{
            background-color: #0066cc;
            color: white;
            padding: 12px 8px;
            text-align: center;
            font-weight: 600;
            border: 1px solid #0052a3;
        }}
        
        td {{
            padding: 10px 8px;
            border: 1px solid #ddd;
            text-align: center;
        }}
        
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        
        code {{
            background-color: #f5f5f5;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.9em;
            color: #c7254e;
        }}
        
        pre {{
            background-color: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            border-left: 3px solid #0066cc;
            overflow-x: auto;
            margin: 15px 0;
            page-break-inside: avoid;
        }}
        
        pre code {{
            background: none;
            padding: 0;
            color: #333;
            font-size: 0.85em;
        }}
        
        hr {{
            border: none;
            border-top: 2px solid #ddd;
            margin: 25px 0;
        }}
        
        strong {{
            font-weight: 600;
            color: #0066cc;
        }}
        
        em {{
            font-style: italic;
            color: #555;
        }}
        
        /* 인쇄 최적화 */
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            
            h1, h2, h3, h4, h5 {{
                page-break-after: avoid;
            }}
            
            table, pre, ul, ol {{
                page-break-inside: avoid;
            }}
            
            a {{
                text-decoration: none;
                color: #333;
            }}
        }}
        
        /* 첫 페이지 스타일 */
        body > h1:first-of-type {{
            text-align: center;
            border: none;
            margin-top: 50px;
            margin-bottom: 40px;
            font-size: 32px;
        }}
        
        /* 박스 스타일 */
        .info-box {{
            background-color: #e8f4fd;
            border-left: 4px solid #0066cc;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
            page-break-inside: avoid;
        }}
        
        .warning-box {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
            page-break-inside: avoid;
        }}
        
        /* 예시 박스 */
        p:has(strong:first-child:contains("예시")) {{
            background-color: #f0f8ff;
            padding: 10px 15px;
            border-radius: 4px;
            margin: 10px 0;
        }}
    </style>
</head>
<body>
{content}

<div style="text-align: center; margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px;">
    <p>본 문서는 2026학년도 대학수학능력시험 공식 자료 및 주요 대학 정시 모집요강을 기준으로 작성되었습니다.</p>
    <p>최종 합격 여부는 각 대학의 공식 발표를 따라야 합니다.</p>
</div>
</body>
</html>'''


def main():
    # Markdown 파일 읽기
    md_path = 'docs/수능_점수_변환_및_추정_방법.md'
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # HTML 변환
    html_content = markdown_to_html(md_content)
    full_html = create_html_with_style(html_content)
    
    # HTML 파일 저장
    html_path = 'docs/수능_점수_변환_및_추정_방법.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(full_html)
    
    print(f"✅ HTML 파일 생성 완료: {html_path}")
    print()
    print("📄 PDF 변환 방법:")
    print("1. 생성된 HTML 파일을 웹 브라우저(Chrome, Safari 등)로 엽니다")
    print("2. 브라우저 메뉴에서 '인쇄' 또는 Cmd+P (Mac) / Ctrl+P (Windows)를 선택합니다")
    print("3. 프린터 대상을 'PDF로 저장'으로 선택합니다")
    print("4. 저장 위치를 선택하고 저장합니다")
    print()
    print("💡 권장 인쇄 설정:")
    print("- 용지 크기: A4")
    print("- 여백: 기본값")
    print("- 배경 그래픽: 포함")
    print("- 축척: 100%")


if __name__ == '__main__':
    main()
