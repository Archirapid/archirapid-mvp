import re, pathlib
path=pathlib.Path('modules/ai_house_designer/babylon_editor.py')
text=path.read_text(encoding='utf-8')
start=text.find('html = f"""')
end=text.find('"""', start+12)
html_text=text[start:end]
open_braces=[m.start() for m in re.finditer(r'(?<!\{)\{(?!\{)', html_text)]
close_braces=[m.start() for m in re.finditer(r'(?<!\})\}(?!\})', html_text)]
print('singles',len(open_braces),len(close_braces))
for idx in open_braces:
    line_no=html_text.count('\n',0,idx)+1
    print('open at',line_no, html_text.splitlines()[line_no-1])
for idx in close_braces:
    line_no=html_text.count('\n',0,idx)+1
    print('close at',line_no, html_text.splitlines()[line_no-1])
