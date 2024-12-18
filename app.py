from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit, join_room
from flask_session import Session
import os
import json
from datetime import datetime

app = Flask(__name__)

# 配置 Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'  # 使用文件系统存储 session
app.config['SECRET_KEY'] = 'your_secret_key'  # 配置 session 密钥
app.config['SESSION_PERMANENT'] = False  # 设置 session 非永久
Session(app)

socketio = SocketIO(app, manage_session=False)

# 用户信息存储文件
USER_FILE = 'users.txt'
# 聊天室信息存储文件
CHATROOMS_FILE = 'chatrooms.json'
# 在线用户存储文件
ONLINE_USERS_FILE = 'online_users.json'
# 聊天记录存储文件夹
CHAT_LOGS_FOLDER = 'chat_logs'

# 确保聊天记录文件夹存在
if not os.path.exists(CHAT_LOGS_FOLDER):
    os.makedirs(CHAT_LOGS_FOLDER)


# 加载用户信息
def get_users():
    if not os.path.exists(USER_FILE):
        return {}

    users = {}
    with open(USER_FILE, 'r') as f:
        for line in f.readlines():
            username, password = line.strip().split(':')
            users[username] = password
    return users


# 加载聊天室数据
def load_chatrooms():
    if os.path.exists(CHATROOMS_FILE):
        with open(CHATROOMS_FILE, 'r') as f:
            return json.load(f)
    return {}


# 加载在线用户数据
def load_online_users():
    if os.path.exists(ONLINE_USERS_FILE):
        with open(ONLINE_USERS_FILE, 'r') as f:
            return json.load(f)
    return {}


# 保存聊天室数据
def save_chatrooms():
    with open(CHATROOMS_FILE, 'w') as f:
        json.dump(chatrooms, f)


# 保存在线用户数据
def save_online_users():
    with open(ONLINE_USERS_FILE, 'w') as f:
        json.dump(online_users, f)


# 保存聊天记录
def save_chat_log(room_name, message):
    log_file = os.path.join(CHAT_LOGS_FOLDER, f"{room_name}.json")
    log_data = {}

    # 如果日志文件存在，读取现有聊天记录
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            log_data = json.load(f)

    # 获取当前时间戳
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 将新消息添加到日志
    if room_name not in log_data:
        log_data[room_name] = []

    log_data[room_name].append({"timestamp": timestamp, "message": message})

    # 保存更新后的聊天记录
    with open(log_file, 'w') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=4)


# 初始化数据
chatrooms = load_chatrooms()
online_users = load_online_users()


# 注册页面
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        users = get_users()
        if username in users:
            flash('Username already exists. Please choose another one.', 'error')
            return redirect(url_for('register'))

        # 将新用户保存到文件
        with open(USER_FILE, 'a') as f:
            f.write(f"{username}:{password}\n")

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# 登录页面
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        users = get_users()
        if username not in users or users[username] != password:
            flash('Invalid username or password.', 'error')
            return redirect(url_for('login'))

        session['username'] = username  # 保存用户名到 session
        flash('Login successful!', 'success')
        return redirect(url_for('chatrooms_page'))

    return render_template('login.html')


# 聊天室选择页面（显示现有聊天室并允许创建新聊天室）
@app.route('/chatrooms', methods=['GET', 'POST'])
def chatrooms_page():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    if request.method == 'POST':
        # 创建新聊天室
        room_name = request.form['room_name']
        if room_name in chatrooms:
            flash('Chatroom already exists. Please choose another name.', 'error')
        else:
            chatrooms[room_name] = []  # 初始化聊天室为空
            save_chatrooms()  # 保存聊天室数据到文件
            # 广播聊天室创建事件
            socketio.emit('new_room_created', {'room_name': room_name}, to=None)

        flash(f'Chatroom "{room_name}" created successfully!', 'success')

    # 将聊天室及其成员信息传递到模板
    return render_template('chatrooms.html', chatrooms=chatrooms, username=username)

# 删除聊天室
@app.route('/delete_chatroom/<room_name>', methods=['POST'])
def delete_chatroom(room_name):
    if 'username' not in session:
        return redirect(url_for('login'))

    # 检查聊天室是否存在
    if room_name not in chatrooms:
        flash('Chatroom not found.', 'error')
        return redirect(url_for('chatrooms_page'))

    # 从聊天室数据中删除该聊天室
    del chatrooms[room_name]
    save_chatrooms()  # 更新聊天室数据

    # 删除对应的聊天记录文件
    log_file = os.path.join(CHAT_LOGS_FOLDER, f"{room_name}.json")
    if os.path.exists(log_file):
        os.remove(log_file)

    flash(f'Chatroom "{room_name}" has been deleted.', 'success')
    return redirect(url_for('chatrooms_page'))


# 进入聊天室
@app.route('/chat/<room_name>')
def chat(room_name):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    # 如果聊天室不存在，重定向回聊天室选择页
    if room_name not in chatrooms:
        flash('Chatroom not found.', 'error')
        return redirect(url_for('chatrooms_page'))

    # 加入聊天室
    if username not in chatrooms[room_name]:
        chatrooms[room_name].append(username)
        save_chatrooms()  # 保存聊天室信息到文件

    # 加载聊天记录
    log_file = os.path.join(CHAT_LOGS_FOLDER, f"{room_name}.json")
    messages = []
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            messages = json.load(f).get(room_name, [])

    # 获取当前聊天室的成员
    members = chatrooms[room_name]

    # 将聊天室成员和历史消息传递给模板
    return render_template('chat.html', username=username, room_name=room_name, members=members, messages=messages)


# 退出聊天室
@app.route('/leave/<room_name>')
def leave_room(room_name):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    if room_name in chatrooms and username in chatrooms[room_name]:
        chatrooms[room_name].remove(username)
        save_chatrooms()  # 保存聊天室信息到文件
        flash(f'You have left the chatroom "{room_name}".', 'success')

    return redirect(url_for('chatrooms_page'))


# 退出登录
@app.route('/logout')
def logout():
    session.pop('username', None)  # 清除 session 中的用户名
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


# 聊天页面主页
@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('chatrooms_page'))


# 处理聊天消息时，包含用户名
@socketio.on('message')
def handle_message(data):
    username = session['username']  # 获取当前登录的用户名
    room_name = data['room_name']
    message = f"{username}: {data['message']}"  # 将用户名和消息内容结合

    # 保存聊天记录
    save_chat_log(room_name, message)

    # 广播消息到房间
    emit('message', message, room=room_name)


@socketio.on('join')
def handle_join(data):
    room_name = data['room']
    username = session['username']

    # 将用户加入房间
    join_room(room_name)

    # 将用户加入聊天室的成员列表
    if username not in chatrooms[room_name]:
        chatrooms[room_name].append(username)
        save_chatrooms()  # 保存聊天室信息到文件

    # 广播更新聊天室成员列表
    emit('update_members', {'members': chatrooms[room_name]}, room=room_name)

    # 广播用户加入聊天室的消息
    emit('message', f"{username} has joined the chat!", room=room_name)

@socketio.on('leave')
def handle_leave(data):
    room_name = data['room']
    username = session['username']

    # 从房间中离开
    leave_room(room_name)

    # 从聊天室成员列表中移除用户
    if username in chatrooms[room_name]:
        chatrooms[room_name].remove(username)
        save_chatrooms()  # 保存聊天室信息到文件

    # 广播更新聊天室成员列表
    emit('update_members', {'members': chatrooms[room_name]}, room=room_name)

    # 广播用户退出聊天室的消息
    emit('message', f"{username} has left the chat.", room=room_name)


@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    if username:
        # 将用户从所有聊天室中移除
        for room_name, members in chatrooms.items():
            if username in members:
                members.remove(username)
        save_chatrooms()  # 更新聊天室信息

# @socketio.on('disconnect')
# def handle_disconnect():
#     username = session.get('username')
#     if username:
#         for room_name in chatrooms:
#             if username in chatrooms[room_name]:
#                 chatrooms[room_name].remove(username)
#                 save_chatrooms()  # 更新聊天室信息
#                 emit('update_members', {'members': chatrooms[room_name]}, room=room_name)



if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)