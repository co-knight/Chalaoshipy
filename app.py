import pandas as pd
import json
import glob
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, abort, jsonify

from config import Config

def load_data():
    try:
        teachers_df = pd.read_csv('data/teachers.csv', keep_default_na=False)
        teachers_df['姓名_lower'] = teachers_df['姓名'].str.lower()
        teachers_df['全拼_lower'] = teachers_df['拼音'].str.lower()
        teachers_df['首字母_lower'] = teachers_df['拼音缩写'].str.lower()
        teachers_df['评分_numeric'] = pd.to_numeric(teachers_df['评分'], errors='coerce')

        comment_files = glob.glob('data/comment_*.csv')
        if not comment_files:
            all_comments_df = pd.DataFrame()
        else:
            all_dfs = [pd.read_csv(f, keep_default_na=False) for f in comment_files]
            all_comments_df = pd.concat(all_dfs, ignore_index=True)

        if not all_comments_df.empty:
            all_comments_df['发表时间'] = pd.to_datetime(all_comments_df['发表时间'], errors='coerce')
            all_comments_df['点赞减去点踩数量'] = pd.to_numeric(all_comments_df['点赞减去点踩数量'], errors='coerce').fillna(0)
            all_comments_df.dropna(subset=['发表时间'], inplace=True)

        with open('data/gpa.json', 'r', encoding='utf-8') as f:
            gpa_data = json.load(f)

        return teachers_df, all_comments_df, gpa_data
    except FileNotFoundError as e:
        app.logger.error(f"核心数据文件未找到 - {e}")
        exit(1)

app = Flask(__name__)
app.config.from_object(Config)

TEACHERS_DF, COMMENTS_DF, GPA_DATA = load_data()

if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    app.logger.setLevel(logging.INFO)
    app.logger.info('应用启动')


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/teacher/<teacher_name>')
def teacher_detail(teacher_name):
    teacher_info_row = TEACHERS_DF[TEACHERS_DF['姓名'] == teacher_name]
    if teacher_info_row.empty:
        app.logger.warning(f"尝试访问不存在的教师: {teacher_name}")
        abort(404)
    teacher_info = teacher_info_row.iloc[0]

    comments = COMMENTS_DF[COMMENTS_DF['老师姓名'] == teacher_name]
    sort_by = request.args.get('sort_by', 'likes')

    if not comments.empty:
        if sort_by == 'time':
            sorted_comments = comments.sort_values(by='发表时间', ascending=False)
        else:
            sorted_comments = comments.sort_values(by='点赞减去点踩数量', ascending=False)
        comments_list = sorted_comments.to_dict('records')
    else:
        comments_list = []

    for comment in comments_list:
        if isinstance(comment.get('内容'), str):
            comment['内容'] = comment['内容'].replace('\\n', '\n')

    teacher_gpa_data = GPA_DATA.get(teacher_name, [])

    return render_template(
        'teacher_detail.html',
        teacher_name=teacher_name,
        teacher_info=teacher_info,
        comments=comments_list,
        gpa_data=teacher_gpa_data
    )

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify([])

    mask = (
        TEACHERS_DF['姓名_lower'].str.contains(query, na=False) |
        TEACHERS_DF['全拼_lower'].str.contains(query, na=False) |
        TEACHERS_DF['首字母_lower'].str.contains(query, na=False)
    )
    results = TEACHERS_DF[mask].sort_values(by='评分_numeric', ascending=False, na_position='last').head(10)
    results['评分_display'] = results['评分_numeric'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")
    search_results = results[['姓名', '学院', '评分_display']].to_dict('records')
    return jsonify(search_results)