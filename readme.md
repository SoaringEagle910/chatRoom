## 多人聊天室系统

这是一个从头开始搭建起来的简单的多人聊天室系统，基于flask框架开发，前端使用HTML和一些简单的CSS。

#### 使用方法
1. 安装python环境
2. 运行`pip install -r requirements.txt`
3. 如果需要使用ai聊天功能，在app.py的28行添加你的api密钥，我使用的是 [free_chatgpt_api](https://github.com/popjane/free_chatgpt_api) 提供的免费api密钥
4. 运行`python app.py`

#### 系统使用说明
1. 启动系统，运行app.py，即可在本机上访问，或通过局域网访问。

2. 访问网页，进入登录界面，可点击先进行注册
![初始页面](pic/2-init.png)

3. 输入用户名和密码进行注册
![注册页面](pic/3-register.png)

4. 注册成功，自动跳转至登录界面，可进行登录
![注册页面](pic/4-login.png)
   
5. 登录成功，进入聊天室选择页面，可在此创建新的聊天室
![聊天室选择页面](pic/5-chatrooms.png)

6. 创建成功
![创建聊天室](pic/6-createChatRoom.png)

7. 点击蓝色的 first room 即可进入聊天室
![聊天页面](pic/7-chat.png)

8. 其他用户可看到新的聊天室和聊天室的在线成员
![看见聊天室情况](pic/8-viewChatRooms.png)

9.  当user1加入后，user0可看到
![看见成员加入](pic/9-knowNewJoin.png)

10. 聊天吧！
![聊天](pic/10-comeChat!.png)

11. 管理员可踢出聊天室的成员
![踢出成员](pic/11-kick.png)
被踢出的成员收到提示并退回至聊天室选择页面
![接收被踢出消息](pic/11-kicked.png)

12. 点击下载按键可下载聊天记录
![下载聊天记录](pic/12-download.png)

13. 可退出当前聊天室，回到选择聊天室界面
![离开聊天室](pic/13-leave.png)

14. 可以点击Edit Description对聊天室的简介进行修改
![修改聊天室简介](pic/14-edit.png)

15. 点击logout可退出登录
![退出登录](pic/15-logout.png)

16. 还可以与ai对话！！！在消息前添加@GPT即可向GPT发问！
![ai对话](pic/16-aiChat.png)

17. 发送后等待GPT回复（目前有阻塞的问题，用户发出消息无法立即显示，要等GPT回复之后才会一起显示）
![ai回复](pic/17-aiResponse.png)