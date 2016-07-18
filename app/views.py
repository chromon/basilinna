# -*- coding: utf-8 -*-

' a test module '

__author__ = 'Ellery'

from flask import Flask, render_template, request, session, abort, redirect, url_for, make_response
from sqlalchemy import and_, func
from app import app, models, csrf
from app.main import valid_account, encryption, invitation, db_service
from datetime import datetime
import json

# register page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        # show the signup form
        return render_template('signup.html')
    elif request.method == 'POST':
        # do the signup
        email = request.form.get('email')
        nickname = request.form.get('nickname')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # whether the email address is exist
        is_exist = valid_account.valid_email_exist(email)
        if is_exist:
            return render_template('signup.html', 
                error_message='该email地址已被注册',
                signup_form=request.form)
        else:
            if password != confirm_password:
                return render_template('signup.html', 
                    error_message='两次密码输入不一致',
                    signup_form=request.form)

            # encryption password
            new_password, salt = encryption.encrypt_pass_salt(password)

            # ip address
            ip = request.remote_addr

            # Invitation link
            invite_string = invitation.invite_url()
            invite_link = app.config.get('HOST') + invite_string

            # initial user and member db data
            u = models.User(email=email, password=new_password, salt=salt,
                create_time=str(datetime.now()), last_login_time=str(datetime.now()),
                last_login_ip=ip, status=1, remark='user', invent=invite_link)
            db_service.db_insert(u)
            db_service.db_commit()
            
            avatar_path = '../static/image/avatar/avatar.png'
            m = models.Member(fullname=nickname, gender=None, avatar_path=avatar_path,
                location=None, hometown=None, description=None, autograph=None,
                personality_url=invite_string, is_email_actived=None, user_id=u.id)
            db_service.db_insert(m)
            db_service.db_commit()

            return redirect(url_for('login', info='注册成功，请先登录'))
    else:
        pass


# login page
@app.route('/login', methods = ['GET', 'POST'])
@app.route('/login/<info>', methods = ['GET', 'POST'])
def login(info=None):
    if request.method == 'POST':
        # do the login
        email = request.form.get('email')
        password = request.form.get('password')
        rememberme = request.form.get('rememberme')

        # encrypt password with salt
        u = models.User.query.filter_by(email=email).first()
        
        # email not exist
        if u is None:
            return render_template('login.html', error_message='当前邮件账户不存在')

        new_pass = encryption.encrypt_pass(password, u.salt)
        if u.password != new_pass:
            return render_template('login.html', error_message='邮件地址或密码错误')

        # render index page with data
        m = models.Member.query.filter_by(user_id=u.id).first()
        session['member_id'] = m.id

        # set cookie
        response = make_response(redirect(url_for('index')))
        if rememberme:
            response.set_cookie('email', email)
            response.set_cookie('password', password)
        else:
            response.delete_cookie('email')
            response.delete_cookie('password')
        return response
    else:
        # show the login form
        email = request.cookies.get('email')
        password = request.cookies.get('password')
        return render_template('login.html', info=info, email=email, password=password)


# index page
@app.route('/', methods=['GET'])
@app.route('/index', methods=['GET'])
def index():
    if 'member_id' in session:
        member_id = session['member_id']
        m = models.Member.query.filter_by(id=member_id).first()
        if m is None:
            redirect(url_for('error'))

        # blog detail
        blog_list = models.Blog.query.filter_by(member_id=member_id).order_by(models.Blog.id.desc()).all()

        blog_info_list = []

        # blog collected
        for blog in blog_list:
            c = models.Collection.query.filter(and_(models.Collection.member_id==member_id, models.Collection.blog_id==blog.id)).first()
            if c is None:
                blog_dict = dict(blog=blog, collection='uncollect', blog_member=m)
            else:
                blog_dict = dict(blog=blog, collection='collecting', blog_member=m)

            # a blog repeat list
            re_list = []

            if blog.post_type == 'REPEAT':
                re_from = None
                re_member_id = None
                
                re_blog = models.Blog.query.filter_by(id=blog.re_from).first()
                re_member = models.Member.query.filter_by(id=blog.re_member_id).first()
                re_list.append(dict(blog=re_blog, blog_member=re_member))

                re_from = re_blog.re_from    
                re_member_id = re_blog.re_member_id

                # exist reblog
                while re_from :
                    re_blog_t = models.Blog.query.filter_by(id=re_from).first()
                    re_member_t = models.Member.query.filter_by(id=re_member_id).first()
                    re_list.append(dict(blog=re_blog_t, blog_member=re_member_t))
                    
                    re_from = re_blog_t.re_from
                    re_member_id = re_blog_t.re_member_id

                blog_dict['re_list'] = re_list

            blog_info_list.append(blog_dict)

        # follow detail
        following_count = models.Relation.query.filter(models.Relation.member_id == m.id).count()
        fans_count = models.Relation.query.filter(models.Relation.followee_id == m.id).count()

        return render_template('index.html', member=m, blog_list=blog_info_list, 
            following_count=following_count, fans_count=fans_count)

    return redirect(url_for('login', info='访问当前内容，请先登录'))


# post blog
@app.route('/post', methods = ['POST'])
def post():
    member_id = session['member_id']

    # get blog content from ajax data
    data = json.loads(request.form.get('data'))
    content = data['content']
    re_from = int(data['re_from'])
    re_member_id = int(data['re_member_id'])
    post_type = data['post_type']

    if re_from == 0:
        re_from = None
    if re_member_id == 0:
        re_member_id = None

    # insert blog
    b = models.Blog(content=content, create_time=str(datetime.now()),
        post_type=post_type, via='Web', exist_pic=0, pic_path=None,
        location=None, member_id=member_id, re_from=re_from, re_member_id=re_member_id)
    db_service.db_insert(b)
    db_service.db_commit()

    # build a blog dict for json
    blog_dict = dict(id=b.id, content=b.content, create_time=str(b.create_time),
        post_type=b.post_type, exist_pic=b.exist_pic, pic_path=b.pic_path, via=b.via)
    temp = json.dumps(blog_dict)

    return temp


# space page
@app.route('/space', methods = ['GET'])
@app.route('/space/<url>', methods = ['GET'])
def space(url=None):
    if request.method == 'GET':
        # current member
        member_id = session['member_id']
        m = models.Member.query.filter_by(id=member_id).first()
        if m is None:
            redirect(url_for('error'))

        if url:
            if url != m.personality_url:
                # selected member space
                selected_member = models.Member.query.filter_by(personality_url=url).first()
                blog_list = models.Blog.query.filter_by(member_id=selected_member.id).order_by(models.Blog.id.desc()).all()

                blog_info_list = []

                # blog collected
                for blog in blog_list:
                    c = models.Collection.query.filter(and_(models.Collection.member_id==selected_member.id, models.Collection.blog_id==blog.id)).first()
                    if c is None:
                        blog_dict = dict(blog=blog, collection='uncollect', blog_member=selected_member)
                    else:
                        blog_dict = dict(blog=blog, collection='collecting', blog_member=selected_member)

                    # a blog repeat list
                    re_list = []

                    if blog.post_type == 'REPEAT':
                        re_from = None
                        re_member_id = None
                        
                        re_blog = models.Blog.query.filter_by(id=blog.re_from).first()
                        re_member = models.Member.query.filter_by(id=blog.re_member_id).first()
                        re_list.append(dict(blog=re_blog, blog_member=re_member))

                        re_from = re_blog.re_from    
                        re_member_id = re_blog.re_member_id

                        # exist reblog
                        while re_from :
                            re_blog_t = models.Blog.query.filter_by(id=re_from).first()
                            re_member_t = models.Member.query.filter_by(id=re_member_id).first()
                            re_list.append(dict(blog=re_blog_t, blog_member=re_member_t))
                            
                            re_from = re_blog_t.re_from
                            re_member_id = re_blog_t.re_member_id

                        blog_dict['re_list'] = re_list

                    blog_info_list.append(blog_dict)

                # follow detail
                following_count = models.Relation.query.filter(models.Relation.member_id == selected_member.id).count()
                fans_count = models.Relation.query.filter(models.Relation.followee_id == selected_member.id).count()

                return render_template('space.html', member=selected_member, blog_list=blog_info_list, 
                    following_count=following_count, fans_count=fans_count)
            else :
                # my space
                blog_list = models.Blog.query.filter_by(member_id=member_id).order_by(models.Blog.id.desc()).all()

                blog_info_list = []

                # blog collected
                for blog in blog_list:
                    c = models.Collection.query.filter(and_(models.Collection.member_id==member_id, models.Collection.blog_id==blog.id)).first()
                    if c is None:
                        blog_dict = dict(blog=blog, collection='uncollect', blog_member=m)
                    else:
                        blog_dict = dict(blog=blog, collection='collecting', blog_member=m)

                    # a blog repeat list
                    re_list = []

                    if blog.post_type == 'REPEAT':
                        re_from = None
                        re_member_id = None
                        
                        re_blog = models.Blog.query.filter_by(id=blog.re_from).first()
                        re_member = models.Member.query.filter_by(id=blog.re_member_id).first()
                        re_list.append(dict(blog=re_blog, blog_member=re_member))

                        re_from = re_blog.re_from    
                        re_member_id = re_blog.re_member_id

                        # exist reblog
                        while re_from :
                            re_blog_t = models.Blog.query.filter_by(id=re_from).first()
                            re_member_t = models.Member.query.filter_by(id=re_member_id).first()
                            re_list.append(dict(blog=re_blog_t, blog_member=re_member_t))
                            
                            re_from = re_blog_t.re_from
                            re_member_id = re_blog_t.re_member_id

                        blog_dict['re_list'] = re_list

                    blog_info_list.append(blog_dict)

                # follow detail
                following_count = models.Relation.query.filter(models.Relation.member_id == m.id).count()
                fans_count = models.Relation.query.filter(models.Relation.followee_id == m.id).count()

                return render_template('space.html', member=m, blog_list=blog_info_list, 
                    following_count=following_count, fans_count=fans_count)
        else:
            # my space
            blog_list = models.Blog.query.filter_by(member_id=member_id).order_by(models.Blog.id.desc()).all()

            blog_info_list = []

            # blog collected
            for blog in blog_list:
                c = models.Collection.query.filter(and_(models.Collection.member_id==member_id, models.Collection.blog_id==blog.id)).first()
                if c is None:
                    blog_dict = dict(blog=blog, collection='uncollect', blog_member=m)
                else:
                    blog_dict = dict(blog=blog, collection='collecting', blog_member=m)

                # a blog repeat list
                re_list = []

                if blog.post_type == 'REPEAT':
                    re_from = None
                    re_member_id = None
                    
                    re_blog = models.Blog.query.filter_by(id=blog.re_from).first()
                    re_member = models.Member.query.filter_by(id=blog.re_member_id).first()
                    re_list.append(dict(blog=re_blog, blog_member=re_member))

                    re_from = re_blog.re_from    
                    re_member_id = re_blog.re_member_id

                    # exist reblog
                    while re_from :
                        re_blog_t = models.Blog.query.filter_by(id=re_from).first()
                        re_member_t = models.Member.query.filter_by(id=re_member_id).first()
                        re_list.append(dict(blog=re_blog_t, blog_member=re_member_t))
                        
                        re_from = re_blog_t.re_from
                        re_member_id = re_blog_t.re_member_id

                    blog_dict['re_list'] = re_list

                blog_info_list.append(blog_dict)

            # follow detail
            following_count = models.Relation.query.filter(models.Relation.member_id == m.id).count()
            fans_count = models.Relation.query.filter(models.Relation.followee_id == m.id).count()

            return render_template('space.html', member=m, blog_list=blog_info_list, 
                following_count=following_count, fans_count=fans_count)

        return redirect(url_for('error'))
    else:
        return redirect(url_for('error'))


# follow people
@app.route('/follow', methods = ['POST'])
def follow():
    if request.method == 'POST':
        member_id = session['member_id']

        # # get followee id from ajax data
        data = json.loads(request.form.get('data'))
        followee_id = data['followee_id']

        # insert relation
        r = models.Relation(member_id=member_id, followee_id=followee_id)
        db_service.db_insert(r)
        db_service.db_commit()

        return 'followsuccess'
    else:
        return redirect(url_for('error'))


# unfollow people
@app.route('/unfollow', methods = ['POST'])
def unfollow():
    if request.method == 'POST':
        member_id = session['member_id']

        # # get followee id from ajax data
        data = json.loads(request.form.get('data'))
        followee_id = data['followee_id']

        # delete relation
        r = models.Relation.query.filter(and_(models.Relation.member_id==member_id, models.Relation.followee_id==followee_id)).first()
        if r is None:
            redirect(url_for('error'))
        db_service.db_delete(r)
        db_service.db_commit()

        return 'unfollowsuccess'
    else:
        return redirect(url_for('error'))


# blog collect
@app.route('/collect', methods = ['POST'])
def collect():
    if request.method == 'POST':
        member_id = session['member_id']

        # get blog id
        data = json.loads(request.form.get('data'))
        blog_id = data['blog_id']

        # insert collection
        c = models.Collection(blog_id=blog_id, member_id=member_id)
        db_service.db_insert(c)
        db_service.db_commit()

        return 'collectsuccess'
    else:
        return redirect(url_for('error'))


# blog uncollect
@app.route('/uncollect', methods = ['POST'])
def uncollect():
    if request.method == 'POST':
        member_id = session['member_id']

        # get blog id
        data = json.loads(request.form.get('data'))
        blog_id = data['blog_id']

        # delete collection
        c = models.Collection.query.filter(and_(models.Collection.member_id==member_id, models.Collection.blog_id==blog_id)).first()
        if c is None:
            redirect(url_for('error'))
        db_service.db_delete(c)
        db_service.db_commit()

        return 'uncollectsuccess'
    else:
        return redirect(url_for('error'))

# blog collections
@app.route('/collections', methods = ['GET', 'POST'])
def collections():
    if request.method == 'GET':
        member_id = session['member_id']
        m = models.Member.query.filter_by(id=member_id).first()
        if m is None:
            redirect(url_for('error'))

        # collections detail
        collection_list = models.Collection.query.filter_by(member_id=member_id).order_by(models.Collection.id.desc()).all()

        blog_list = []

        # blog collected
        for collection in collection_list:
            b = models.Blog.query.filter_by(id=collection.blog_id).first()
            
            # blog author
            collect_member = None
            if b.member_id != m.id:
                # not mine
                collect_member = modles.Member.query.filter_by(id=b.member_id).first()
            else:
                collect_member = m
            blog_dict = dict(blog=b, collect_member=collect_member)

            blog_list.append(blog_dict)

        # follow detail
        following_count = models.Relation.query.filter(models.Relation.member_id == m.id).count()
        fans_count = models.Relation.query.filter(models.Relation.followee_id == m.id).count()

        return render_template('collections.html', member=m, blog_list=blog_list, 
            following_count=following_count, fans_count=fans_count)
    elif request.method == 'POST':
        return 'hah'


# blog delete
@app.route('/delpost', methods = ['POST'])
def delpost():
    if request.method == 'POST':
        member_id = session['member_id']

        # get blog id
        data = json.loads(request.form.get('data'))
        blog_id = data['blog_id']

        # delete post
        b = models.Blog.query.filter_by(id=blog_id).first()
        if b is None:
            redirect(url_for('error'))
        db_service.db_delete(b)
        db_service.db_commit()

        return 'delpostsuccess'
    else:
        return redirect(url_for('error'))


# private message
@app.route('/messages', methods = ['GET', 'POST'])
def messages():
    if request.method == 'GET':
        return render_template('messages.html')
    elif request.method == 'POST':
        pass
    else:
        return redirect(url_for('error'))

# explore
@app.route('/explore', methods = ['GET', 'POST'])
def explore():
    if request.method == 'GET':
        return render_template('explore.html')
    elif request.method == 'POST':
        pass
    else:
        return redirect(url_for('error'))

# search
@app.route('/search', methods = ['GET', 'POST'])
def search():
    if request.method == 'GET':
        return render_template('search.html')
    elif request.method == 'POST':
        pass
    else:
        return redirect(url_for('error'))

# setting
@app.route('/setting', methods = ['GET', 'POST'])
def setting():
    if request.method == 'GET':
        return render_template('setting.html')
    elif request.method == 'POST':
        pass
    else:
        return redirect(url_for('error'))

# logout
@app.route('/logout', methods = ['GET'])
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login', info='注销成功，请重新登录'))

# error
@app.route('/error', methods = ['GET'])
def sys_error():
    return render_template('error_sys.html')

@app.errorhandler(404)
def page_not_found(error):
    return render_template('error_404.html'), 404

@app.errorhandler(500)
def server_syntax_error(error):
    return render_template('error_500.html'), 500

@csrf.error_handler
def csrf_error(reason):
    return render_template('error_csrf.html', reason=reason), 400