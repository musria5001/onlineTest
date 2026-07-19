import smtplib
from email.mime.text import MIMEText

def sendmail(receiver,subject,content):
    email_host = 'localhost'     # 发送者是qq邮箱
    email_user = 'xuejing@c.njupt.edu.cn'  # 发送者账号
    email_pwd = 'hunter'       # 发送者密码
    maillist = receiver    # 接收者账号，本来想写成[]list的，但是报错，还没解决！
    me = email_user

    msg = MIMEText(content, 'html', 'utf-8')    # 邮件内容，三个参数：第一个为文本内容，第二个 html 设置文本格式，第三个 utf-8 设置编码
    msg['Subject'] = subject    # 邮件主题
    msg['From'] = me    # 发送者账号
    msg['To'] = maillist    # 接收者账号列表（列表没实现）

    smtp = smtplib.SMTP(email_host,25) # 如上变量定义的，是qq邮箱
    smtp.ehlo()
    smtp.starttls()
    # smtp.login(email_user, email_pwd)   # 发送者的邮箱账号，密码
    smtp.login(None,None)
    smtp.sendmail(me, maillist, msg.as_string())    # 参数分别是发送者，接收者，第三个不知道
    smtp.quit() # 发送完毕后退出smtp
    print ('email send success.')

sendmail('xuejing_cn@163.com','Hello','Hi')
