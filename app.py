from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit, join_room, leave_room as socket_leave_room
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 配置 session 密钥
socketio = SocketIO(app)

# 用户信息存储文件
USER_FILE = 'users.txt'
# 聊天室信息存储（以字典形式存储每个聊天室的用户列表）
chatrooms = {}

# 存储用户信息
def get_users():
    if not os.path.exists(USER_FILE):
        return {}

    users = {}
    with open(USER_FILE, 'r') as f:
        for line in f.readlines():
            username, password = line.strip().split(':')
            users[username] = password
    return users

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
            # 广播新聊天室创建事件
            socketio.emit('new_room_created', {'room_name': room_name}, broadcast=True)

        flash(f'Chatroom "{room_name}" created successfully!', 'success')

    # 将聊天室及其成员信息传递到模板
    return render_template('chatrooms.html', chatrooms=chatrooms, username=username)

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
        # 广播用户加入聊天室事件
        socketio.emit('user_joined', {'room_name': room_name, 'username': username}, broadcast=True)

    # 将聊天室成员传递给模板
    members = chatrooms[room_name]
    return render_template('chat.html', username=username, room_name=room_name, members=members)

# 退出聊天室
@app.route('/leave/<room_name>')
def leave_room(room_name):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    if room_name in chatrooms and username in chatrooms[room_name]:
        chatrooms[room_name].remove(username)
        # 广播用户离开聊天室事件
        socketio.emit('user_left', {'room_name': room_name, 'username': username}, broadcast=True)
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

    # 广播消息到房间
    emit('message', message, room=room_name)

# 处理用户加入聊天室
@socketio.on('join')
def handle_join(data):
    room_name = data['room']
    username = session['username']

    # 将用户加入房间
    join_room(room_name)

    # 广播用户加入聊天室的消息
    emit('message', f"{username} has joined the chat!", room=room_name)

# 处理用户离开聊天室
@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    if username:
        # 将用户从所有聊天室中移除
        for room_name, members in chatrooms.items():
            if username in members:
                members.remove(username)
                # 广播用户离开聊天室事件
                socketio.emit('user_left', {'room_name': room_name, 'username': username}, broadcast=True)

# 监听客户端断开连接事件，清理聊天室成员
@socketio.on('disconnect')
def on_disconnect():
    username = session.get('username')
    if username:
        # 清除用户在所有聊天室中的成员身份
        for room_name in chatrooms:
            if username in chatrooms[room_name]:
                chatrooms[room_name].remove(username)
                socketio.emit('user_left', {'room_name': room_name, 'username': username}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)