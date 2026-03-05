import importlib
from modules.ai_house_designer import babylon_editor
importlib.reload(babylon_editor)
from modules.ai_house_designer.babylon_editor import generate_babylon_html
rooms_data=[{'name':'A','code':'A','area_m2':10}]
html=generate_babylon_html(rooms_data, 10, 10)
print('success, length', len(html))
