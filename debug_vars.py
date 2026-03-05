import json
rooms_data=[{'name':'A','code':'A','area_m2':10}]
total_width=10
total_depth=10
roof_type="Dos aguas (clásico, eficiente)"
plot_area_m2=0
foundation_type="Losa de hormigón (suelos blandos)"
house_style="Moderno"
print('types', type(rooms_data), type(total_width), type(total_depth), type(roof_type), type(plot_area_m2), type(foundation_type), type(house_style))
rooms_js = json.dumps(rooms_data, ensure_ascii=False)
print('rooms_js type', type(rooms_js))
try:
    test = f"abc {rooms_js} def"
    print('small fstring ok')
except Exception as e:
    print('error small',e)
try:
    html_test = f"rooms:{rooms_js}, w:{total_width}, d:{total_depth}, roof:{roof_type}, plot:{plot_area_m2}, found:{foundation_type}, style:{house_style}"
    print('big test ok', html_test[:60])
except Exception as e:
    print('error big',e)
