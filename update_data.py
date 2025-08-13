import requests
import hashlib
import zipfile
import os
import sys
import argparse
import getpass

EXTRACT_TO_DIR = 'data'
TOKEN_URL = "https://openid.cc98.org/connect/token"
API_BASE_URL = "https://api.cc98.org"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# 输出错误信息并退出程序。
def error_exit(message):
    print(f"\n[错误] {message}", file=sys.stderr)
    sys.exit(1)

# 使用OAuth 2.0获取access_token。
def get_access_token(username, password, client_id, client_secret):
    print("\n[步骤 2] 正在通过 API 获取访问令牌 (Access Token)...")
    
    token_payload = {
        'grant_type': 'password',
        'username': username,
        'password': password,
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'cc98-api openid offline_access',
    }
    
    try:
        response = requests.post(TOKEN_URL, data=token_payload, headers=HEADERS)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            error_message = token_data.get('error_description') or token_data.get('error') or '未知错误'
            error_exit(f"获取 Access Token 失败: {error_message}")
            
        print("[成功] 已成功获取 Access Token。")
        return access_token
        
    except requests.exceptions.RequestException as e:
        error_exit(f"获取Token时发生网络错误: {e}")
    except ValueError:
        error_exit(f"无法解析来自Token服务器的响应，响应内容: {response.text}")

# 校验文件的SHA256哈希值。
def verify_zip_hash(zip_filename, expected_hash):
    if not expected_hash:
        print("[信息] 未提供哈希值，跳过文件完整性校验。")
        return

    print(f"\n[步骤 3] 正在校验 '{zip_filename}' 的哈希值...")
    sha256_hash = hashlib.sha256()
    try:
        with open(zip_filename, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        actual_hash = sha256_hash.hexdigest()

        print(f"  - 文件实际 SHA256: {actual_hash}")
        print(f"  - 期望 SHA256: {expected_hash}")

        if actual_hash.lower() != expected_hash.lower():
            error_exit("文件哈希值不匹配！文件可能已损坏或不是正确的文件。")
        else:
            print("[成功] 文件哈希值校验成功。")
    except FileNotFoundError:
        error_exit(f"文件 '{zip_filename}' 不存在。")
    except Exception as e:
        error_exit(f"读取文件时发生错误: {e}")

# 使用API从指定主题和楼层获取内容。
def fetch_content_from_api(access_token, topic_id, floor_number):
    print(f"\n[步骤 4] 正在调用API获取内容...")
    print(f"  - 主题ID: {topic_id}")
    print(f"  - 目标楼层: {floor_number}")

    page_size = 10
    start_index = (floor_number - 1) // page_size * page_size
    
    api_url = f"{API_BASE_URL}/Topic/{topic_id}/post?from={start_index}&size={page_size}"
    print(f"  - 构造的API URL: {api_url}")

    auth_headers = HEADERS.copy()
    auth_headers['Authorization'] = f'Bearer {access_token}'

    try:
        response = requests.get(api_url, headers=auth_headers, timeout=20)
        response.raise_for_status()
        
        posts_data = response.json()

        target_post = None
        for post in posts_data:
            if post.get('floor') == floor_number:
                target_post = post
                break
        
        if not target_post:
            error_exit(f"在API返回的数据中找不到楼层号为 {floor_number} 的帖子。")

        content = target_post.get('content')
        if not content:
            error_exit("找到了目标楼层，但其'content'字段为空。")

        import re
        plain_text_content = re.sub(r'\[.*?\]', '', content).strip()

        print(f"[成功] 已成功从API提取内容: \"{plain_text_content}\"")
        return plain_text_content

    except requests.exceptions.RequestException as e:
        error_exit(f"调用API时发生网络错误: {e}")
    except (ValueError, KeyError) as e:
        error_exit(f"解析API响应时发生错误: {e}。响应内容: {response.text}")


def run_update_process():
    print("[步骤 1] 请输入更新所需的信息:")
    zip_filename = input("  - 请输入ZIP文件名 (例如 data.zip): ")
    sha256_optional = input("  - 请输入SHA256校验值 (可选, 直接回车跳过): ")
    
    topic_id = input("  - 请输入目标主题ID (Topic ID, 例如 5399305): ")
    floor_str = input("  - 请输入楼层号 (例如 3164): ")
    
    if not os.path.exists(zip_filename):
        error_exit(f"文件 '{zip_filename}' 在当前目录不存在。")

    try:
        floor_number = int(floor_str)
    except ValueError:
        error_exit(f"楼层号 '{floor_str}' 不是一个有效的数字。")

    client_id = "9a1fd200-8687-44b1-4c20-08d50a96e5cd"
    client_secret = "8b53f727-08e2-4509-8857-e34bf92b27f2"
    cc98_username = input("  - 请输入您的 CC98 用户名: ")
    cc98_password = getpass.getpass("  - 请输入您的 CC98 密码: ")
    
    access_token = get_access_token(cc98_username, cc98_password, client_id, client_secret)

    verify_zip_hash(zip_filename, sha256_optional)
    
    content_for_password = fetch_content_from_api(access_token, topic_id, floor_number)
    
    print("\n[步骤 5] 正在根据提取的内容生成解压密码...")
    password = hashlib.sha256(content_for_password.encode('utf-8')).hexdigest()
    print("[成功] 解压密码已生成。")

    print(f"\n[步骤 6] 正在解压 '{zip_filename}' 到 '{EXTRACT_TO_DIR}' 目录...")
    if not os.path.exists(EXTRACT_TO_DIR):
        os.makedirs(EXTRACT_TO_DIR)
        print(f"  - 已创建目录: '{EXTRACT_TO_DIR}'")
    
    try:
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_TO_DIR, pwd=password.encode('utf-8'))
        print(f"[成功] 文件已成功解压到 '{EXTRACT_TO_DIR}' 目录。")
    except RuntimeError as e:
        if 'Bad password' in str(e):
            error_exit("解压失败！密码错误。请检查主题ID和楼层号是否正确。")
        else:
            error_exit(f"解压时发生未知运行时错误: {e}")
    except Exception as e:
        error_exit(f"解压时发生错误: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="ChalaoshiPy 数据更新工具。使用 --update 参数启动交互式向导。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--update',
        action='store_true',
        help="更新数据工具"
    )
    
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    
    if args.update:
        run_update_process()

if __name__ == '__main__':
    main()
