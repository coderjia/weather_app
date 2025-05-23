from flask import Flask, render_template, request, send_file
import requests
import pandas as pd
from io import BytesIO

app = Flask(__name__)
dataframe_global = None

def get_coordinates(city):
    """使用 Open-Meteo Geo API 获取经纬度"""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&format=json"
    try:
        # 添加verify=False参数禁用SSL验证（仅用于测试）
        r = requests.get(url, timeout=10, verify=False)
        results = r.json().get('results')
        if results:
            return results[0]['latitude'], results[0]['longitude']
    except Exception as e:
        print(f"获取坐标时出错: {e}")
    return None, None

@app.route('/', methods=['GET', 'POST'])
def index():
    global dataframe_global
    table_html = None

    if request.method == 'POST':
        city_list = request.form['cities'].split(',')
        start_date = request.form['start_date']
        end_date = request.form['end_date']

        weather_data = {}

        for city in city_list:
            city = city.strip()
            lat, lon = get_coordinates(city)
            if lat is None:
                continue

            url = (
                f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
                f"&start_date={start_date}&end_date={end_date}"
                f"&daily=temperature_2m_min,temperature_2m_max&timezone=Asia/Shanghai"
            )

            r = requests.get(url)
            result = r.json()

            if 'daily' in result:
                temps = [
                    f"{min_t}℃ ~ {max_t}℃"
                    for min_t, max_t in zip(result['daily']['temperature_2m_min'], result['daily']['temperature_2m_max'])
                ]
                weather_data[city] = temps
                if 'date' not in weather_data:
                    weather_data['date'] = result['daily']['time']

        if 'date' in weather_data:
            # 创建DataFrame但不立即设置索引
            df = pd.DataFrame(weather_data)
            # 保存一个副本用于Excel下载
            df_for_excel = df.copy()
            df_for_excel = df_for_excel.set_index('date')
            df_for_excel.index.name = '日期'
            dataframe_global = df_for_excel
            
            # 不使用pandas的to_html方法，而是完全手动构建表格
            dates = df['date'].tolist()
            cities = [col for col in df.columns if col != 'date']
            
            # 构建表格HTML
            table_html = '<table class="data" border="1">\n'
            
            # 表头行
            table_html += '  <thead>\n    <tr>\n'
            table_html += '      <th>日期</th>\n'  # 日期列标题
            
            # 添加城市名称作为列标题
            for city in cities:
                table_html += f'      <th>{city}</th>\n'
            table_html += '    </tr>\n  </thead>\n'
            
            # 表格内容
            table_html += '  <tbody>\n'
            for i in range(len(dates)):
                table_html += '    <tr>\n'
                table_html += f'      <td>{dates[i]}</td>\n'  # 日期值
                
                # 添加每个城市的温度数据
                for city in cities:
                    table_html += f'      <td>{df[city][i]}</td>\n'
                table_html += '    </tr>\n'
            table_html += '  </tbody>\n</table>'


    return render_template('index.html', table=table_html)

@app.route('/download')
def download():
    global dataframe_global
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter', datetime_format='yyyy-mm-dd') as writer:
        df_to_save = dataframe_global.copy()
        # 索引是日期，格式化成字符串，保持索引名为"日期"
        df_to_save.index = pd.to_datetime(df_to_save.index).strftime('%Y-%m-%d')
        df_to_save.index.name = '日期'
        df_to_save.to_excel(writer, sheet_name='Weather', index=True)

    output.seek(0)
    return send_file(output, download_name="weather.xlsx", as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
