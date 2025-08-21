import pandas as pd
import json
import glob
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, abort, jsonify
import time
from functools import lru_cache

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

TEACHERS_DF['search_blob'] = (
    TEACHERS_DF['姓名_lower'].astype(str) + '|' +
    TEACHERS_DF['全拼_lower'].astype(str) + '|' +
    TEACHERS_DF['首字母_lower'].astype(str)
)

def _normalize_q(q: str) -> str:
    return (q or '').strip().lower()

@lru_cache(maxsize=1024)
def _search_core(q_norm: str, limit: int):
    if not q_norm:
        return []
    mask = TEACHERS_DF['search_blob'].str.contains(q_norm, na=False, regex=False)
    if not mask.any():
        return []
    df_top = TEACHERS_DF.loc[mask, ['姓名', '学院', '评分_numeric']]
    df_top = df_top.nlargest(limit, '评分_numeric')
    df_top = df_top.copy()
    df_top['评分_display'] = df_top['评分_numeric'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")
    return df_top[['姓名', '学院', '评分_display']].to_dict('records')

def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

COURSE_TO_TEACHERS = {}
for teacher_name_key, courses in GPA_DATA.items():
    for course_entry in courses:
        if not course_entry:
            continue
        course_name = course_entry[0] if len(course_entry) > 0 else None
        if not course_name:
            continue
        avg_gpa = to_float(course_entry[1] if len(course_entry) > 1 else None)
        total_count = to_int(course_entry[2] if len(course_entry) > 2 else None)
        std_gpa = to_float(course_entry[3] if len(course_entry) > 3 else None)
        COURSE_TO_TEACHERS.setdefault(course_name, []).append({
            'teacher': teacher_name_key,
            'avg_gpa': avg_gpa,
            'std_gpa': std_gpa,
            'total_count': total_count
        })

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
    t0 = time.perf_counter()
    q_raw = request.args.get('q', '')
    q_norm = _normalize_q(q_raw)[:64]
    if not q_norm:
        return jsonify([])
    try:
        limit_param = int(request.args.get('limit', 10))
    except (TypeError, ValueError):
        limit_param = 10
    limit = min(max(limit_param, 1), 25)

    result = _search_core(q_norm, limit)
    dur_ms = (time.perf_counter() - t0) * 1000
    try:
        app.logger.info(f"/api/search q='{q_norm[:32]}' limit={limit} hits={len(result)} dur_ms={dur_ms:.1f}")
    except Exception:
        pass
    return jsonify(result)

@app.route('/api/course_teachers')
def api_course_teachers():
    course_name = request.args.get('course', '')
    exclude_teacher = request.args.get('exclude', '')
    if not course_name:
        return jsonify([])

    entries = COURSE_TO_TEACHERS.get(course_name, [])
    result = []
    for entry in entries:
        teacher_name_val = entry.get('teacher')
        if exclude_teacher and teacher_name_val == exclude_teacher:
            continue

        college = None
        rating = None
        rating_count = None
        hot = None

        row = TEACHERS_DF[TEACHERS_DF['姓名'] == teacher_name_val]
        if not row.empty:
            r = row.iloc[0]
            college = r.get('学院') if '学院' in r else None
            rating = r.get('评分_numeric') if '评分_numeric' in r else None
            rating = float(rating) if pd.notna(rating) else None
            rating_count = to_int(r.get('评分人数') if '评分人数' in r else None)
            hot = to_int(r.get('热度') if '热度' in r else None)

        result.append({
            'teacher': teacher_name_val,
            'college': college,
            'rating': rating,
            'rating_count': rating_count,
            'hot': hot,
            'avg_gpa': entry.get('avg_gpa'),
            'std_gpa': entry.get('std_gpa'),
            'total_count': entry.get('total_count')
        })

    def sort_key(x):
        avg = x['avg_gpa'] if x['avg_gpa'] is not None else float('-inf')
        rate = x['rating'] if x['rating'] is not None else float('-inf')
        total = x['total_count'] if x['total_count'] is not None else float('-inf')
        return (avg, rate, total)

    result.sort(key=sort_key, reverse=True)
    return jsonify(result)