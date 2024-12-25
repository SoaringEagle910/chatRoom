from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit, join_room
from flask_session import Session
import os
import json
from datetime import datetime
import os
import openai

app = Flask(__name__)

# 配置 Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'  # 使用文件系统存储 session
app.config['SECRET_KEY'] = 'ZhiWenChatroom'  # 配置 session 密钥
app.config['SESSION_PERMANENT'] = False  # 设置 session 非永久
Session(app)

socketio = SocketIO(app, manage_session=False)

# 用户信息存储文件
USER_FILE = 'data/users.txt'
# 聊天室信息存储文件
CHATROOMS_FILE = 'data/chatrooms.json'
# 聊天记录存储文件夹
CHAT_LOGS_FOLDER = 'data/chat_logs'

# optional; defaults to `os.environ['OPENAI_API_KEY']`
openai.api_key = "your api key from https://github.com/popjane/free_chatgpt_api"
# all client options can be configured just like the `OpenAI` instantiation counterpart
openai.base_url = "https://free.gpt.ge/v1/"
# openai.default_headers = {"x-foo": "true"}
# 初始化对话记录
gpt_messages = []

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


# 保存聊天室数据
def save_chatrooms():
    with open(CHATROOMS_FILE, 'w') as f:
        json.dump(chatrooms, f, ensure_ascii=False, indent=4)



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

# 聊天室创建
@app.route('/chatrooms', methods=['GET', 'POST'])
def chatrooms_page():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    if request.method == 'POST':
        # 创建新聊天室
        room_name = request.form['room_name']
        description = request.form['description']  # 获取聊天室介绍
        if room_name in chatrooms:
            flash('Chatroom already exists. Please choose another name.', 'error')
        else:
            chatrooms[room_name] = {
                'members': [],  # 初始化成员为空
                'description': description  # 存储聊天室的介绍
            }
            save_chatrooms()  # 保存聊天室数据到文件
            # 广播聊天室创建事件
            socketio.emit('new_room_created', {'room_name': room_name, 'description': description}, to=None)

        flash(f'Chatroom "{room_name}" created successfully!', 'success')

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

    # 广播聊天室删除事件给所有用户
    socketio.emit('chatroom_deleted', {'room': room_name}, to=None)

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
    if username not in chatrooms[room_name]['members']:
        chatrooms[room_name]['members'].append(username)
        save_chatrooms()  # 保存聊天室信息到文件

    # 加载聊天记录
    log_file = os.path.join(CHAT_LOGS_FOLDER, f"{room_name}.json")
    messages = []
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            messages = json.load(f).get(room_name, [])

    # 获取当前聊天室的成员
    members = chatrooms[room_name]['members']

    # 获取聊天室的描述
    description = chatrooms[room_name].get('description', 'No description available.')

    # 将聊天室成员、历史消息和聊天室描述传递给模板
    return render_template('chat.html', username=username, room_name=room_name, members=members, messages=messages, description=description)


# 退出聊天室
@app.route('/leave/<room_name>')
def leave_room(room_name):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    if room_name in chatrooms and username in chatrooms[room_name]['members']:
        chatrooms[room_name]['members'].remove(username)
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


def chat_with_ai(question):
    # 将用户问题添加到消息列表
    gpt_messages.append({
        "role": "user",
        "content": question
    })

    completion = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=gpt_messages,
    )

    # 获取并打印 ChatGPT 的回复
    reply = completion.choices[0].message.content
    print("ChatGPT: " + reply)

    # 将 ChatGPT 的回复添加到消息列表
    gpt_messages.append({
        "role": "assistant",
        "content": reply
    })
    return reply


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

    # chat with gpt
    # 提取消息内容部分，去掉用户名和冒号（即提取实际消息）
    user_message = data['message']

    # 判断消息是否以 "@GPT:" 开头
    if user_message.startswith('@GPT'):
        # 获取 "@GPT:" 后的内容
        gpt_question = user_message[len('@GPT'):].strip()  # 去掉 "@GPT:" 和前后空格
        # print("to gpt: " + gpt_question)  # 打印 "@GPT:" 后的内容
        gpt_response = chat_with_ai(gpt_question)
        # print("gpt response: " + gpt_response)
        gpt_message = "GPT: " + gpt_response
        save_chat_log(room_name, gpt_message)
        emit('message', gpt_message, room=room_name)


@socketio.on('join')
def handle_join(data):
    room_name = data['room']
    username = session['username']

    # 将用户加入房间
    join_room(room_name)

    # 将用户加入聊天室的成员列表
    if username not in chatrooms[room_name]['members']:
        chatrooms[room_name]['members'].append(username)
        save_chatrooms()

    # 广播更新聊天室成员列表给所有客户端
    emit('update_members', {'room': room_name, 'members': chatrooms[room_name]['members']}, broadcast=True)

    # 广播用户加入聊天室的消息
    emit('message', f"{username} has joined the chat.", room=room_name)


@socketio.on('leave')
def handle_leave(data):
    room_name = data['room']
    username = session['username']

    # 从房间中离开
    leave_room(room_name)

    # 从聊天室成员列表中移除用户
    if username in chatrooms[room_name]['members']:
        chatrooms[room_name]['members'].remove(username)
        save_chatrooms()  # 保存聊天室信息到文件

    # 广播更新聊天室成员列表给所有客户端
    emit('update_members', {'room': room_name, 'members': chatrooms[room_name]['members']}, broadcast=True)

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
                # 广播更新聊天室成员列表
                emit('update_members', {'members': members, 'room': room_name}, room=room_name)

        # 保存更新后的聊天室信息
        save_chatrooms()  # 更新聊天室信息


@app.route('/edit_chatroom_description/<room_name>', methods=['POST'])
def edit_chatroom_description(room_name):
    if 'username' not in session:
        return redirect(url_for('login'))

    # 检查聊天室是否存在
    if room_name not in chatrooms:
        flash('Chatroom not found.', 'error')
        return redirect(url_for('chatrooms_page'))

    # 获取新的聊天室描述
    new_description = request.form['new_description']

    # 更新聊天室描述
    chatrooms[room_name]['description'] = new_description
    save_chatrooms()  # 保存更新后的聊天室数据

    flash('Chatroom description updated successfully!', 'success')

    # 广播聊天室描述更新事件
    socketio.emit('chatroom_description_updated', {'room': room_name, 'description': new_description}, to=None)

    return redirect(url_for('chatrooms_page'))


# 处理踢出用户事件
@socketio.on('kick')
def handle_kick(data):
    room_name = data['room']
    kicked_user = data['member']
    username = session['username']

    # 确保只有聊天室的管理员或创建者能踢出成员
    if username not in chatrooms[room_name]['members']:
        return  # 不是成员无法踢出

    # 确保被踢出的用户存在于聊天室中
    if kicked_user in chatrooms[room_name]['members']:
        # 从聊天室成员中移除被踢出的用户
        chatrooms[room_name]['members'].remove(kicked_user)
        save_chatrooms()  # 更新聊天室数据

        # 广播更新后的成员列表
        emit('update_members', {'room': room_name, 'members': chatrooms[room_name]['members']}, broadcast=True)

        # 通知被踢出的用户
        emit('message', f"{kicked_user} has been kicked out of the chatroom.", broadcast=True)

        # 发送离开事件给被踢出的用户，确保其跳转到聊天室页面
        emit('kick_out', {'room': room_name, 'member': kicked_user}, broadcast=True)


from flask import jsonify, request
@app.route('/download-chat-log')
def download_chat_log():
    room_name = request.args.get('room_name')  # 获取 URL 中的 room_name 参数
    if room_name:
        # 构造聊天记录文件的路径
        chat_log_file = os.path.join(CHAT_LOGS_FOLDER, f'{room_name}.json')
        if os.path.exists(chat_log_file):
            with open(chat_log_file, 'r') as file:
                chat_log = json.load(file)
            return jsonify(chat_log)  # 返回聊天记录的 JSON 数据
        else:
            return jsonify({"error": f"Chat log for room '{room_name}' not found."}), 404
    else:
        return jsonify({"error": "Room name not provided."}), 400


if __name__ == '__main__':
    print("智问聊天室已部署！访问端口: 10.250.9.172:5000")
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)